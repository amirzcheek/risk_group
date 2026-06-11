# -*- coding: utf-8 -*-
"""
Модель группы риска: LightGBM + калибровка + вклад факторов.

Ключевые решения:
  * LightGBM (gradient boosting) на табличных признаках. GPU не нужна.
  * Дисбаланс классов (отчисляются — меньшинство) обрабатываем через
    scale_pos_weight = (нег/поз).
  * Валидация ПО КОГОРТАМ ВО ВРЕМЕНИ: обучаемся на ранних учебных периодах,
    проверяемся на поздних (не случайный train/test split).
  * Калибровка вероятностей (isotonic) по валидационной когорте — чтобы число
    «риск = 0.7» можно было трактовать как вероятность.
  * Объяснимость: вклад факторов через LightGBM pred_contrib (это точные
    значения Шепли для деревьев) — эдвайзер видит, ПОЧЕМУ студент во флаге.
  * Настраиваемый порог: топ-X% по вероятности → флаг (см. config.RISK_TOP_FRACTION).

Артефакты сохраняются в config.MODEL_DIR:
  model.txt          — бустер LightGBM,
  calibrator.pkl     — калибратор вероятностей,
  model_meta.json    — метаданные обучения (фичи, периоды, метрики, порог).
"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from features import FEATURE_COLUMNS, FEATURE_DOC, feature_matrix

CALIBRATOR_PATH = os.path.join(config.MODEL_DIR, "calibrator.pkl")


@dataclass
class ModelBundle:
    """Обёртка над обученной моделью: бустер, калибратор и метаданные."""

    booster: object
    calibrator: object | None
    feature_columns: list[str]
    meta: dict

    # ── Прогноз ──
    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Калиброванная вероятность отчисления для каждой строки."""
        X = feature_matrix(df[self.feature_columns]) if set(self.feature_columns).issubset(df.columns) else feature_matrix(df)
        raw = self.booster.predict(X.values)
        raw = np.asarray(raw, dtype=float)
        if self.calibrator is not None:
            return np.clip(self.calibrator.predict(raw), 0.0, 1.0)
        return raw

    # ── Объяснимость: вклад факторов ──
    def contributions(self, df: pd.DataFrame) -> np.ndarray:
        """Матрица вкладов признаков (n строк × n признаков) в лог-оддсы риска."""
        X = feature_matrix(df) if not set(self.feature_columns).issubset(df.columns) else feature_matrix(df[self.feature_columns])
        contrib = self.booster.predict(X.values, pred_contrib=True)
        # Последний столбец — базовое значение (intercept), отбрасываем.
        return np.asarray(contrib)[:, :-1]

    def top_factors(self, df: pd.DataFrame, k: int = 5) -> list[list[dict]]:
        """Для каждой строки — топ-k факторов, ПОВЫШАЮЩИХ риск.

        Возвращает список (по строкам) списков {feature, description, value,
        contribution}, отсортированных по убыванию вклада в риск.
        """
        contrib = self.contributions(df)
        result = []
        values = df[self.feature_columns].reset_index(drop=True)
        for i in range(len(df)):
            row = []
            order = np.argsort(contrib[i])[::-1]  # по убыванию вклада в риск
            for j in order[:k]:
                c = float(contrib[i][j])
                if c <= 0:
                    continue  # показываем только то, что ТОЛКАЕТ в группу риска
                fname = self.feature_columns[j]
                row.append(
                    {
                        "feature": fname,
                        "description": FEATURE_DOC.get(fname, fname),
                        "value": round(float(values.iloc[i][fname]), 3),
                        "contribution": round(c, 4),
                    }
                )
            result.append(row)
        return result


def _time_split(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Делит периоды на обучение/валидацию по времени (последний период — валид.)."""
    terms = sorted(df["term"].unique())
    if len(terms) < 2:
        return terms, terms
    # Последний период — валидация; можно расширить до последних двух.
    n_val = 1 if len(terms) <= 4 else 2
    return terms[:-n_val], terms[-n_val:]


def train(
    df: pd.DataFrame | None = None,
    cutoff: int | None = None,
    top_fraction: float | None = None,
) -> ModelBundle:
    """Обучает модель на данных признаков с валидацией по когортам во времени."""
    import lightgbm as lgb
    from sklearn.isotonic import IsotonicRegression

    cutoff = cutoff if cutoff is not None else config.CUTOFF_WEEK
    top_fraction = top_fraction if top_fraction is not None else config.RISK_TOP_FRACTION

    if df is None:
        from features import build_training_frame
        df = build_training_frame(cutoff)

    train_terms, val_terms = _time_split(df)
    tr = df[df["term"].isin(train_terms)]
    va = df[df["term"].isin(val_terms)]

    X_tr, y_tr = feature_matrix(tr), tr["label"].values
    X_va, y_va = feature_matrix(va), va["label"].values

    # Обработка дисбаланса: вес положительного класса = нег/поз.
    pos = max(1, int(y_tr.sum()))
    neg = max(1, int((y_tr == 0).sum()))
    scale_pos_weight = neg / pos

    params = {
        "objective": "binary",
        "metric": ["average_precision", "auc"],
        "learning_rate": 0.03,
        "num_leaves": 31,
        "min_child_samples": 40,
        "feature_fraction": 0.85,
        "bagging_fraction": 0.85,
        "bagging_freq": 1,
        "scale_pos_weight": scale_pos_weight,
        "verbose": -1,
        "seed": 42,
    }
    dtrain = lgb.Dataset(X_tr.values, label=y_tr, feature_name=FEATURE_COLUMNS)
    dval = lgb.Dataset(X_va.values, label=y_va, reference=dtrain)

    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=600,
        valid_sets=[dtrain, dval],
        valid_names=["train", "valid"],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )

    # ── Калибровка вероятностей по валидационной когорте (isotonic) ──
    raw_val = np.asarray(booster.predict(X_va.values), dtype=float)
    calibrator = None
    if len(np.unique(y_va)) == 2:
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_val, y_va)

    # ── Порог: топ-X% по вероятности на валидации → флаг группы риска ──
    proba_val = calibrator.predict(raw_val) if calibrator is not None else raw_val
    threshold = float(np.quantile(proba_val, 1.0 - top_fraction)) if len(proba_val) else 0.5

    meta = {
        "trained_at_utc": _now_iso(),
        "feature_columns": FEATURE_COLUMNS,
        "cutoff_week": cutoff,
        "top_fraction": top_fraction,
        "threshold": threshold,
        "train_terms": train_terms,
        "valid_terms": val_terms,
        "n_train": int(len(tr)),
        "n_valid": int(len(va)),
        "train_pos_rate": float(y_tr.mean()),
        "valid_pos_rate": float(y_va.mean()) if len(y_va) else 0.0,
        "scale_pos_weight": scale_pos_weight,
        "best_iteration": int(booster.best_iteration or booster.current_iteration()),
        "lightgbm_params": {k: v for k, v in params.items() if k != "metric"},
    }
    return ModelBundle(booster, calibrator, FEATURE_COLUMNS, meta)


def save(bundle: ModelBundle) -> None:
    """Сохраняет артефакты модели в config.MODEL_DIR."""
    os.makedirs(config.MODEL_DIR, exist_ok=True)
    bundle.booster.save_model(config.MODEL_PATH, num_iteration=bundle.booster.best_iteration)
    with open(config.MODEL_META_PATH, "w", encoding="utf-8") as f:
        json.dump(bundle.meta, f, ensure_ascii=False, indent=2)
    with open(CALIBRATOR_PATH, "wb") as f:
        pickle.dump(bundle.calibrator, f)


def load() -> ModelBundle:
    """Загружает артефакты модели из config.MODEL_DIR."""
    import lightgbm as lgb

    if not os.path.exists(config.MODEL_PATH):
        raise FileNotFoundError(
            "Модель не обучена. Запустите: python train.py (или POST /train)."
        )
    booster = lgb.Booster(model_file=config.MODEL_PATH)
    with open(config.MODEL_META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    calibrator = None
    if os.path.exists(CALIBRATOR_PATH):
        with open(CALIBRATOR_PATH, "rb") as f:
            calibrator = pickle.load(f)
    return ModelBundle(booster, calibrator, meta["feature_columns"], meta)


def risk_level(proba: float, meta: dict) -> str:
    """Текстовый уровень риска для UI: high / medium / low."""
    if proba >= config.RISK_THRESHOLD_HIGH:
        return "high"
    if proba >= max(config.RISK_THRESHOLD_MEDIUM, 0):
        return "medium"
    return "low"


def _now_iso() -> str:
    """Текущее время UTC в ISO. Вынесено для совместимости окружений."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
