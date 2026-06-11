# -*- coding: utf-8 -*-
"""
End-to-end прогон всего пайплайна на синтетических данных.

Шаги: генерация синтетики → признаки → обучение → скоринг → метрики.
Удобно для первичной проверки, что всё связано и работает без Платонуса и без
живого LLM.

Запуск:
    python run_pipeline.py
    python run_pipeline.py --students 1500 --seed 7
"""

from __future__ import annotations

import argparse

import config


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end прогон пайплайна на синтетике")
    parser.add_argument("--students", type=int, default=1300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-generate", action="store_true", help="не перегенерировать синтетику")
    args = parser.parse_args()

    if not args.skip_generate:
        print("\n=== ШАГ 1. Генерация синтетических данных ===")
        from synthetic_data import generate, write_csv

        tables = generate(n_students=args.students, seed=args.seed)
        write_csv(tables, config.SYNTHETIC_DIR)
        print(f"Готово: {config.SYNTHETIC_DIR}")

    print("\n=== ШАГ 2-4. Обучение модели + метрики ===")
    import train

    train.run_training()

    print("\n=== ШАГ 5. Батч-скоринг ===")
    import scoring
    import storage

    run = scoring.run_scoring()
    print(f"Прогон: {run['run_id']}, в группе риска: {run['n_flagged']}/{run['n_students']}")
    print(f"Хранилище: {storage.backend_name()}")

    print("\n=== ШАГ 6. Пример списка риска (топ-5) ===")
    items = storage.get_risk_list(only_flagged=True)[:5]
    for it in items:
        factors = ", ".join(f["feature"] for f in it["top_factors"][:3])
        print(f"  {it['student_id']} [{it['study_group']}] риск={it['risk_proba']:.2f} "
              f"({it['risk_level']}) — {factors}")

    print("\nПайплайн завершён успешно.")


if __name__ == "__main__":
    main()
