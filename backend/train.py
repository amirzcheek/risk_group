# -*- coding: utf-8 -*-
"""
Переобучение модели группы риска и сохранение артефакта.

Шаги:
  1. Построить матрицу признаков с метками (временной срез без утечки).
  2. Обучить LightGBM с валидацией по когортам во времени.
  3. Сохранить бустер, калибратор и метаданные в config.MODEL_DIR.
  4. Посчитать и вывести метрики на валидации.

Запуск:
    python train.py
    python train.py --cutoff 6 --top-fraction 0.10
"""

from __future__ import annotations

import argparse

import config
import model as model_mod
from evaluate import evaluate, _print_report
from features import build_training_frame


def run_training(cutoff: int | None = None, top_fraction: float | None = None) -> dict:
    """Полный цикл обучения. Возвращает метаданные + метрики."""
    cutoff = cutoff if cutoff is not None else config.CUTOFF_WEEK
    print(f"[1/4] Построение признаков (неделя отсечки = {cutoff})…")
    df = build_training_frame(cutoff)
    pos = int(df["label"].sum())
    print(f"      Наблюдений: {len(df)}, отчислений: {pos} ({pos/len(df):.1%})")

    print("[2/4] Обучение LightGBM (валидация по когортам во времени)…")
    bundle = model_mod.train(df, cutoff=cutoff, top_fraction=top_fraction)

    print("[3/4] Сохранение артефакта модели…")
    model_mod.save(bundle)
    print(f"      Модель: {config.MODEL_PATH}")
    print(f"      Метаданные: {config.MODEL_META_PATH}")

    print("[4/4] Оценка качества на валидации…")
    metrics = evaluate(bundle, df)
    _print_report(metrics)
    return {"meta": bundle.meta, "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description="Обучение модели группы риска")
    parser.add_argument("--cutoff", type=int, default=None, help="неделя отсечки (по умолч. из env)")
    parser.add_argument("--top-fraction", type=float, default=None, help="доля флага (топ-X%)")
    args = parser.parse_args()
    run_training(cutoff=args.cutoff, top_fraction=args.top_fraction)


if __name__ == "__main__":
    main()
