# -*- coding: utf-8 -*-
"""
Генератор синтетических данных студентов с историей и метками отчисления.

Назначение: собрать и протестировать ВЕСЬ пайплайн (признаки → модель → скоринг →
бэкенд → фронт) ДО подключения реального Платонуса. Данные имитируют то, что
вернули бы запросы из data_queries.yaml, и пишутся в backend/data/raw/*.csv —
ровно с теми же колонками, что ожидает слой доступа к данным (platonus.py).

Модель порождения данных физически осмысленна:
  * у каждого студента есть устойчивые скрытые черты (способности, вовлечённость);
  * слабые способности и низкая вовлечённость → хуже баллы, ниже посещаемость,
    больше просрочек, реже входы в LMS, провалы по ключевым предметам;
  * из этих же скрытых черт (плюс курс, форма обучения, динамика) формируется
    риск отчисления → событие expelled на одной из недель семестра.

Признаки строятся ПОЗЖЕ, на состояние до недели отсечки, а метка — это отчисление
СТРОГО ПОЗЖЕ отсечки. Поэтому в данных есть реальный обучаемый сигнал, но без
утечки будущего (см. features.py).

Запуск:
    python synthetic_data.py            # сгенерировать в backend/data/raw
    python synthetic_data.py --students 1500 --seed 7
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

import config

# Учебные периоды по возрастанию во времени. Ранние идут в обучение, поздние —
# в валидацию (проверка по когортам во времени, см. train.py).
TERMS = ["2022-2", "2023-1", "2023-2", "2024-1", "2024-2", "2025-1"]
WEEKS_PER_TERM = 15
COURSES = ["MATH101", "PHYS102", "PROG103", "ENG104", "PHED105"]
KEY_COURSES = {"MATH101", "PROG103"}  # профилирующие дисциплины
PASS_SCORE = 50  # порог зачёта балла

FACULTIES = {
    "Факультет ИТ": ["ИТ-21", "ИТ-22", "ИТ-23", "ВТ-21", "ВТ-22"],
    "Факультет экономики": ["ЭК-21", "ЭК-22", "ФН-21", "ФН-22"],
    "Факультет спорта": ["СП-21", "СП-22", "ТР-21", "ТР-22"],
    "Факультет педагогики": ["ПД-21", "ПД-22", "ПС-21"],
}
PROGRAMS = {
    "Факультет ИТ": "Информационные системы",
    "Факультет экономики": "Экономика и финансы",
    "Факультет спорта": "Физическая культура и спорт",
    "Факультет педагогики": "Педагогика и психология",
}
REGIONS = ["Астана", "Алматы", "Шымкент", "Караганда", "Актобе", "Область"]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate(n_students: int = 1300, seed: int = 42) -> dict[str, pd.DataFrame]:
    """Генерирует синтетические таблицы. Возвращает словарь имя→DataFrame."""
    rng = np.random.default_rng(seed)

    # ── Пул студентов с устойчивыми скрытыми чертами ──
    faculties = list(FACULTIES.keys())
    student_ids = [f"S{100000 + i}" for i in range(n_students)]

    fac_choice = rng.choice(faculties, size=n_students, p=[0.34, 0.26, 0.22, 0.18])
    groups = np.array(
        [rng.choice(FACULTIES[f]) for f in fac_choice]
    )
    gender = rng.choice(["М", "Ж"], size=n_students, p=[0.55, 0.45])
    region = rng.choice(REGIONS, size=n_students)
    funding = rng.choice(["грант", "платное"], size=n_students, p=[0.6, 0.4])

    # Скрытые черты студента (стандартизованные). Сохраняются между семестрами.
    ability = rng.normal(0, 1, n_students)        # академические способности
    engagement = rng.normal(0, 1, n_students)     # вовлечённость/мотивация
    # GPA при поступлении коррелирует со способностями.
    entry_gpa = np.clip(2.6 + 0.45 * ability + rng.normal(0, 0.3, n_students), 1.0, 4.0)

    base = pd.DataFrame(
        {
            "student_id": student_ids,
            "faculty": fac_choice,
            "study_group": groups,
            "program": [PROGRAMS[f] for f in fac_choice],
            "gender": gender,
            "region": region,
            "funding_type": funding,
            "entry_gpa": entry_gpa.round(2),
            "_ability": ability,
            "_engagement": engagement,
        }
    )
    # Год рождения и год поступления (для возраста/курса).
    base["admission_year"] = rng.choice([2021, 2022, 2023], size=n_students)
    base["birth_year"] = (base["admission_year"] - 18 - rng.integers(0, 3, n_students)).astype(int)

    students_rows = []
    grades_rows = []
    attendance_rows = []
    submissions_rows = []
    activity_rows = []
    status_rows = []

    for ti, term in enumerate(TERMS):
        # Каждый студент учится не во всех периодах: моделируем, что часть пула
        # активна в данном семестре (приход/уход когорт во времени).
        active_mask = rng.random(n_students) < 0.62
        idx = np.where(active_mask)[0]

        for i in idx:
            sid = student_ids[i]
            ability_i = base["_ability"].iat[i]
            engage_i = base["_engagement"].iat[i]
            # Курс студента в этом семестре (грубо по году поступления).
            course_year = int(np.clip(2025 - base["admission_year"].iat[i] + ti // 2 - 2, 1, 4)) or 1
            course_year = max(1, min(4, course_year))

            # Семестровый шок к вовлечённости (события жизни, нагрузка).
            term_shock = rng.normal(0, 0.6)
            eff_engage = engage_i + term_shock

            # Тренд внутри семестра: у части студентов вовлечённость падает.
            decline = rng.normal(-0.02, 0.06)  # средний слабый спад
            if eff_engage < -0.5:
                decline -= 0.05  # у невовлечённых спад сильнее

            # ── Скрытый риск отчисления на этот семестр ──
            risk_logit = (
                -3.1
                - 1.15 * ability_i
                - 1.0 * eff_engage
                + 1.4 * max(0.0, -decline * 12)        # выраженный спад
                + (0.55 if course_year == 1 else 0.0)  # первокурсники рискованнее
                + (0.30 if funding[i] == "платное" else 0.0)
                + (0.25 if region[i] == "Область" else 0.0)
                + rng.normal(0, 0.4)
            )
            p_drop = float(_sigmoid(np.array([risk_logit]))[0])
            will_drop = rng.random() < p_drop

            # Неделя события отчисления (если будет) — смещена к концу семестра.
            drop_week = None
            if will_drop:
                drop_week = int(np.clip(round(rng.triangular(3, 11, WEEKS_PER_TERM)), 3, WEEKS_PER_TERM))

            students_rows.append(
                {
                    "student_id": sid,
                    "faculty": base["faculty"].iat[i],
                    "study_group": base["study_group"].iat[i],
                    "program": base["program"].iat[i],
                    "course_year": course_year,
                    "gender": base["gender"].iat[i],
                    "birth_year": int(base["birth_year"].iat[i]),
                    "admission_year": int(base["admission_year"].iat[i]),
                    "funding_type": base["funding_type"].iat[i],
                    "region": base["region"].iat[i],
                    "entry_gpa": float(base["entry_gpa"].iat[i]),
                    "term": term,
                }
            )

            # До недели отчисления студент ещё «в системе»; после — данных нет.
            last_week = drop_week if drop_week is not None else WEEKS_PER_TERM

            for w in range(1, last_week + 1):
                # Текущий уровень = базовая вовлечённость + накопленный спад.
                cur = eff_engage + decline * w
                # ── Посещаемость ──
                classes_total = int(rng.integers(8, 14))
                att_rate = float(np.clip(_sigmoid(1.2 * cur + 0.6), 0.05, 0.99))
                attended = int(rng.binomial(classes_total, att_rate))
                attendance_rows.append(
                    {
                        "student_id": sid, "term": term, "week": w,
                        "classes_total": classes_total, "classes_attended": attended,
                    }
                )
                # ── Активность в LMS ──
                lam = max(0.2, 4.0 * _sigmoid(cur))
                activity_rows.append(
                    {
                        "student_id": sid, "term": term, "week": w,
                        "lms_logins": int(rng.poisson(lam)),
                        "material_views": int(rng.poisson(lam * 2.0)),
                    }
                )
                # ── Сдачи заданий (есть не каждую неделю) ──
                if w % 2 == 0:
                    on_time_p = float(np.clip(_sigmoid(1.0 * cur + 0.3), 0.05, 0.98))
                    submitted = int(rng.random() < min(0.99, on_time_p + 0.15))
                    on_time = int(submitted and (rng.random() < on_time_p))
                    submissions_rows.append(
                        {
                            "student_id": sid, "term": term, "week": w,
                            "is_submitted": submitted, "on_time": on_time,
                        }
                    )
                # ── Оценки по предметам (контрольные точки каждые 3 недели) ──
                if w % 3 == 0:
                    for course in COURSES:
                        key = course in KEY_COURSES
                        # Балл зависит от способностей, текущей вовлечённости и
                        # сложности (ключевые предметы строже).
                        mean = 62 + 14 * ability_i + 8 * cur - (8 if key else 0)
                        score = float(np.clip(rng.normal(mean, 12), 0, 100))
                        is_retake = int(score < PASS_SCORE and rng.random() < 0.4)
                        grades_rows.append(
                            {
                                "student_id": sid, "term": term, "week": w,
                                "course_code": course, "is_key_course": int(key),
                                "score": round(score, 1), "is_retake": is_retake,
                                "passed": int(score >= PASS_SCORE),
                            }
                        )

            # ── Событие статуса ──
            if drop_week is not None:
                status_rows.append(
                    {
                        "student_id": sid, "term": term, "week": drop_week,
                        "event_type": "expelled",
                        "reason": rng.choice(
                            ["академическая неуспеваемость", "по собственному желанию",
                             "финансовая задолженность", "длительные пропуски"]
                        ),
                    }
                )
            else:
                status_rows.append(
                    {"student_id": sid, "term": term, "week": WEEKS_PER_TERM,
                     "event_type": "active", "reason": ""}
                )

    tables = {
        "students": pd.DataFrame(students_rows),
        "grades": pd.DataFrame(grades_rows),
        "attendance": pd.DataFrame(attendance_rows),
        "submissions": pd.DataFrame(submissions_rows),
        "activity": pd.DataFrame(activity_rows),
        "status_events": pd.DataFrame(status_rows),
    }
    return tables


def write_csv(tables: dict[str, pd.DataFrame], out_dir: str) -> None:
    """Сохраняет таблицы в CSV (имитация выгрузки из Платонуса)."""
    os.makedirs(out_dir, exist_ok=True)
    for name, df in tables.items():
        path = os.path.join(out_dir, f"{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Генерация синтетических данных студентов")
    parser.add_argument("--students", type=int, default=1300, help="размер пула студентов")
    parser.add_argument("--seed", type=int, default=42, help="seed генератора")
    parser.add_argument("--out", default=config.SYNTHETIC_DIR, help="каталог для CSV")
    args = parser.parse_args()

    tables = generate(n_students=args.students, seed=args.seed)
    write_csv(tables, args.out)

    drop_rate = (tables["status_events"]["event_type"] == "expelled").mean()
    print("Синтетические данные сгенерированы в:", args.out)
    for name, df in tables.items():
        print(f"  {name:14s}: {len(df):>7d} строк")
    print(f"  Доля отчислений (по событиям): {drop_rate:.1%}")
    print(f"  Учебные периоды: {', '.join(TERMS)}")


if __name__ == "__main__":
    main()
