# -*- coding: utf-8 -*-
"""
Батч-скоринг группы риска (еженедельный прогон).

Шаги:
  1. Построить признаки текущих студентов на неделю отсечки (последний период).
  2. Загрузить артефакт модели и посчитать калиброванную вероятность риска.
  3. Определить флаг группы риска по порогу топ-X% (управление нагрузкой).
  4. Для каждого студента собрать топ-факторы (объяснение «почему»).
  5. Записать прогнозы и метаданные прогона в Postgres/SQLite.

Запуск:
    python scoring.py
    python scoring.py --term 2025-1
"""

from __future__ import annotations

import argparse

import numpy as np

import config
import model as model_mod
import storage
from features import build_scoring_frame


def _run_id(term: str) -> str:
    """Идентификатор прогона. Время берём из БД/окружения детерминированно."""
    # Используем модельную версию + период; уникальность обеспечивает счётчик в БД.
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run-{term}-{stamp}"


def run_scoring(term: str | None = None, top_fraction: float | None = None) -> dict:
    """Выполняет батч-скоринг и сохраняет результат. Возвращает сводку прогона."""
    bundle = model_mod.load()
    cutoff = bundle.meta.get("cutoff_week", config.CUTOFF_WEEK)
    top_fraction = top_fraction if top_fraction is not None else bundle.meta.get(
        "top_fraction", config.RISK_TOP_FRACTION
    )

    df = build_scoring_frame(cutoff=cutoff, term=term)
    if df.empty:
        raise RuntimeError("Нет студентов для скоринга (пустой период).")

    term = df["term"].iloc[0]
    proba = bundle.predict_proba(df)
    factors = bundle.top_factors(df, k=5)

    # Флаг группы риска: топ-X% по вероятности в этом прогоне.
    n = len(df)
    n_flag = max(1, int(round(n * top_fraction)))
    threshold = float(np.sort(proba)[::-1][n_flag - 1])
    flagged = proba >= threshold

    rows = []
    for i in range(n):
        rows.append(
            {
                "student_id": df["student_id"].iloc[i],
                "term": term,
                "faculty": df["faculty"].iloc[i],
                "study_group": df["study_group"].iloc[i],
                "program": df["program"].iloc[i],
                "risk_proba": round(float(proba[i]), 4),
                "risk_level": model_mod.risk_level(float(proba[i]), bundle.meta),
                "is_flagged": bool(flagged[i]),
                "top_factors": factors[i],
            }
        )

    run = {
        "run_id": _run_id(term),
        "term": term,
        "cutoff_week": cutoff,
        "n_students": n,
        "n_flagged": int(flagged.sum()),
        "threshold": round(threshold, 4),
        "model_version": bundle.meta.get("trained_at_utc", "unknown"),
    }
    storage.save_run(run, rows)
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description="Батч-скоринг группы риска")
    parser.add_argument("--term", default=None, help="период (по умолч. — последний)")
    parser.add_argument("--top-fraction", type=float, default=None, help="доля флага (топ-X%)")
    args = parser.parse_args()
    run = run_scoring(term=args.term, top_fraction=args.top_fraction)
    print("Скоринг завершён:")
    print(f"  Прогон     : {run['run_id']}")
    print(f"  Период     : {run['term']}  (неделя отсечки {run['cutoff_week']})")
    print(f"  Студентов  : {run['n_students']}")
    print(f"  В группе риска (флаг): {run['n_flagged']}  (порог {run['threshold']})")
    print(f"  Хранилище  : {storage.backend_name()}")


if __name__ == "__main__":
    main()
