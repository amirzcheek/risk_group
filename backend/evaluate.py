# -*- coding: utf-8 -*-
"""
Оценка качества модели группы риска.

Классы несбалансированы (отчисляются — меньшинство), поэтому accuracy НЕ
показателен. Считаем метрики, важные для раннего предупреждения:
  * PR-AUC (average precision) — основная метрика при дисбалансе;
  * ROC-AUC — для сравнения;
  * recall по группе риска при пороге топ-X% (сколько реальных отчислений поймали);
  * precision при том же пороге (какая доля флагов оправдана);
  * recall@k для нескольких k (топ-5/10/20%) — управление нагрузкой эдвайзеров;
  * базовая частота положительного класса (для сравнения с lift);
  * калибровка вероятностей (надёжность чисел риска) по бинам.

Оценка идёт по ВАЛИДАЦИОННЫМ когортам во времени (поздние периоды), которые
модель при обучении не видела.

Запуск:
    python evaluate.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

import config

# На Windows консоль по умолчанию в cp1251 и падает на части символов Unicode.
# Принудительно переводим вывод в UTF-8 (без влияния на работу сервера).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass
import model as model_mod
from features import build_training_frame, feature_matrix


def recall_at_k(y_true: np.ndarray, scores: np.ndarray, k_fraction: float) -> dict:
    """Recall и precision, если флагнуть топ-k_fraction по вероятности."""
    n = len(scores)
    if n == 0:
        return {"recall": 0.0, "precision": 0.0, "n_flagged": 0}
    n_flag = max(1, int(round(n * k_fraction)))
    order = np.argsort(scores)[::-1]
    flagged = order[:n_flag]
    tp = int(y_true[flagged].sum())
    total_pos = int(y_true.sum())
    recall = tp / total_pos if total_pos else 0.0
    precision = tp / n_flag if n_flag else 0.0
    return {"recall": recall, "precision": precision, "n_flagged": n_flag}


def calibration_table(y_true: np.ndarray, proba: np.ndarray, bins: int = 5) -> list[dict]:
    """Таблица калибровки: средняя предсказанная вероятность vs факт по бинам."""
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for b in range(bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (proba >= lo) & (proba < hi) if b < bins - 1 else (proba >= lo) & (proba <= hi)
        if mask.sum() == 0:
            continue
        rows.append(
            {
                "bin": f"[{lo:.1f}, {hi:.1f})",
                "n": int(mask.sum()),
                "pred_mean": round(float(proba[mask].mean()), 3),
                "actual_rate": round(float(y_true[mask].mean()), 3),
            }
        )
    return rows


def evaluate(bundle: model_mod.ModelBundle | None = None, df: pd.DataFrame | None = None) -> dict:
    """Считает метрики на валидационных когортах. Возвращает словарь метрик."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    bundle = bundle or model_mod.load()
    if df is None:
        df = build_training_frame(bundle.meta.get("cutoff_week", config.CUTOFF_WEEK))

    val_terms = bundle.meta.get("valid_terms") or sorted(df["term"].unique())[-1:]
    va = df[df["term"].isin(val_terms)].reset_index(drop=True)
    y = va["label"].values.astype(int)
    proba = bundle.predict_proba(va)

    base_rate = float(y.mean()) if len(y) else 0.0
    pr_auc = float(average_precision_score(y, proba)) if len(np.unique(y)) == 2 else float("nan")
    roc_auc = float(roc_auc_score(y, proba)) if len(np.unique(y)) == 2 else float("nan")

    top_frac = bundle.meta.get("top_fraction", config.RISK_TOP_FRACTION)
    at_threshold = recall_at_k(y, proba, top_frac)

    metrics = {
        "valid_terms": val_terms,
        "n_valid": int(len(va)),
        "n_positives": int(y.sum()),
        "base_rate": round(base_rate, 4),
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc_lift_over_base": round(pr_auc / base_rate, 2) if base_rate else None,
        "threshold_fraction": top_frac,
        "recall_at_threshold": round(at_threshold["recall"], 4),
        "precision_at_threshold": round(at_threshold["precision"], 4),
        "recall_at_k": {
            f"top_{int(k*100)}%": round(recall_at_k(y, proba, k)["recall"], 4)
            for k in (0.05, 0.10, 0.20)
        },
        "precision_at_k": {
            f"top_{int(k*100)}%": round(recall_at_k(y, proba, k)["precision"], 4)
            for k in (0.05, 0.10, 0.20)
        },
        "calibration": calibration_table(y, proba),
    }
    return metrics


def _print_report(m: dict) -> None:
    print("=" * 62)
    print("  ОЦЕНКА КАЧЕСТВА МОДЕЛИ ГРУППЫ РИСКА")
    print("=" * 62)
    print(f"  Валидационные периоды : {', '.join(m['valid_terms'])}")
    print(f"  Наблюдений            : {m['n_valid']}  (отчислений: {m['n_positives']})")
    print(f"  Базовая частота риска : {m['base_rate']:.1%}")
    print("-" * 62)
    print(f"  PR-AUC (average prec.): {m['pr_auc']:.4f}   (lift к базе x{m['pr_auc_lift_over_base']})")
    print(f"  ROC-AUC               : {m['roc_auc']:.4f}")
    print("-" * 62)
    print(f"  При пороге топ-{int(m['threshold_fraction']*100)}% по риску:")
    print(f"    recall (поймано отчислений)  : {m['recall_at_threshold']:.1%}")
    print(f"    precision (оправдано флагов)  : {m['precision_at_threshold']:.1%}")
    print("-" * 62)
    print("  Recall@k / Precision@k:")
    for k in m["recall_at_k"]:
        print(f"    {k:8s}: recall {m['recall_at_k'][k]:.1%}   precision {m['precision_at_k'][k]:.1%}")
    print("-" * 62)
    print("  Калибровка (predicted vs actual):")
    print(f"    {'бин':12s} {'n':>5s} {'pred':>7s} {'actual':>8s}")
    for r in m["calibration"]:
        print(f"    {r['bin']:12s} {r['n']:>5d} {r['pred_mean']:>7.3f} {r['actual_rate']:>8.3f}")
    print("=" * 62)


def main() -> None:
    m = evaluate()
    _print_report(m)
    print("\nJSON:")
    print(json.dumps(m, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
