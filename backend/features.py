# -*- coding: utf-8 -*-
"""
Feature engineering с временным срезом БЕЗ утечки данных (data leakage).

Главный принцип
---------------
Признаки описывают состояние студента на момент N — недели отсечки CUTOFF_WEEK
(по умолчанию 6-я неделя семестра). В признаки попадают ТОЛЬКО события с
week <= CUTOFF_WEEK. Целевая метка — отчисление (expelled) СТРОГО ПОЗЖЕ отсечки
(week > CUTOFF_WEEK). Никакие будущие данные в признаки не просачиваются.

Из набора скоринга исключаются наблюдения, где студент уже выбыл к отсечке
(expelled/academic_leave с week <= CUTOFF_WEEK): на момент N его уже нет, флаг
не нужен.

Каждый признак задокументирован в FEATURE_DOC (имя → человеческое описание),
чтобы эдвайзер и аудит понимали смысл и точку отсечки во времени.

Функции:
  * build_training_frame(cutoff)  — матрица признаков + метка `label` + `term`
    (для обучения и оценки по когортам во времени).
  * build_scoring_frame(cutoff)   — матрица признаков для ПОСЛЕДНЕГО периода без
    метки (текущие студенты, которых скорим на этой неделе).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
import platonus

# ── Документация признаков: имя → (описание, точка отсечки) ──
FEATURE_DOC: dict[str, str] = {
    "entry_gpa": "GPA/балл при поступлении (статический признак)",
    "course_year": "Курс обучения (1..4); первокурсники в среднем рискованнее",
    "age": "Возраст студента на момент периода",
    "is_paid": "Форма обучения платная (1) / грант (0)",
    "is_region": "Иногородний/областной студент (1/0)",
    "is_male": "Пол: мужской (1) / женский (0)",
    "avg_score": "Средний балл по контрольным точкам до недели отсечки",
    "min_score": "Минимальный балл до отсечки (провал по предмету)",
    "score_trend": "Динамика балла: наклон по неделям до отсечки (спад < 0)",
    "key_course_fail_rate": "Доля непройденных контрольных по ключевым предметам",
    "fail_rate": "Доля непройденных контрольных точек (score < порога)",
    "retake_count": "Число пересдач до отсечки",
    "attendance_rate": "Доля посещённых занятий до отсечки",
    "attendance_trend": "Динамика посещаемости по неделям (спад < 0)",
    "absent_weeks": "Число недель с посещаемостью ниже 50%",
    "late_or_missing_rate": "Доля заданий, сданных не в срок или не сданных",
    "missing_count": "Число несданных заданий до отсечки",
    "activity_mean": "Среднее число входов в LMS в неделю до отсечки",
    "activity_trend": "Динамика активности в LMS по неделям (спад < 0)",
    "low_activity_weeks": "Число недель с почти нулевой активностью",
    "course_load": "Число дисциплин с оценками (учебная нагрузка)",
}

# Список колонок-признаков (порядок фиксирован для модели).
FEATURE_COLUMNS = list(FEATURE_DOC.keys())

# Категориальные/демографические признаки, которые добавим для среза по факультету
# (в обучение не идут как фичи модели, но нужны для UI и группировок).
META_COLUMNS = ["student_id", "term", "faculty", "study_group", "program"]


def _trend(weeks: np.ndarray, values: np.ndarray) -> float:
    """Наклон линейного тренда value(week). Отрицательный наклон = спад."""
    if len(values) < 2 or np.all(weeks == weeks[0]):
        return 0.0
    # МНК-наклон; устойчив к малому числу точек.
    slope = np.polyfit(weeks.astype(float), values.astype(float), 1)[0]
    return float(slope)


def _cut(df: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    """Оставляет только события до недели отсечки включительно (без утечки)."""
    if df.empty:
        return df
    return df[df["week"] <= cutoff]


def _aggregate(
    tables: dict[str, pd.DataFrame], cutoff: int
) -> pd.DataFrame:
    """Считает признаки на состояние до недели отсечки для каждого (student, term)."""
    students = tables["students"].copy()
    grades = _cut(tables["grades"], cutoff)
    attendance = _cut(tables["attendance"], cutoff)
    submissions = _cut(tables["submissions"], cutoff)
    activity = _cut(tables["activity"], cutoff)

    students["key"] = students["student_id"] + "|" + students["term"]

    feats: dict[str, dict] = {row.key: {} for row in students.itertuples()}

    # ── Оценки ──
    if not grades.empty:
        grades = grades.copy()
        grades["key"] = grades["student_id"] + "|" + grades["term"]
        for key, g in grades.groupby("key"):
            d = feats.setdefault(key, {})
            d["avg_score"] = float(g["score"].mean())
            d["min_score"] = float(g["score"].min())
            d["score_trend"] = _trend(g["week"].values, g["score"].values)
            d["fail_rate"] = float((g["passed"] == 0).mean())
            key_g = g[g["is_key_course"] == 1]
            d["key_course_fail_rate"] = (
                float((key_g["passed"] == 0).mean()) if not key_g.empty else 0.0
            )
            d["retake_count"] = int(g["is_retake"].sum())
            d["course_load"] = int(g["course_code"].nunique())

    # ── Посещаемость ──
    if not attendance.empty:
        attendance = attendance.copy()
        attendance["key"] = attendance["student_id"] + "|" + attendance["term"]
        attendance["rate"] = attendance["classes_attended"] / attendance["classes_total"].clip(lower=1)
        for key, a in attendance.groupby("key"):
            d = feats.setdefault(key, {})
            total = a["classes_total"].sum()
            attended = a["classes_attended"].sum()
            d["attendance_rate"] = float(attended / total) if total else 0.0
            weekly = a.groupby("week")["rate"].mean()
            d["attendance_trend"] = _trend(weekly.index.values, weekly.values)
            d["absent_weeks"] = int((weekly < 0.5).sum())

    # ── Сдачи заданий ──
    if not submissions.empty:
        submissions = submissions.copy()
        submissions["key"] = submissions["student_id"] + "|" + submissions["term"]
        for key, s in submissions.groupby("key"):
            d = feats.setdefault(key, {})
            n = len(s)
            late_or_missing = ((s["is_submitted"] == 0) | (s["on_time"] == 0)).sum()
            d["late_or_missing_rate"] = float(late_or_missing / n) if n else 0.0
            d["missing_count"] = int((s["is_submitted"] == 0).sum())

    # ── Активность в LMS ──
    if not activity.empty:
        activity = activity.copy()
        activity["key"] = activity["student_id"] + "|" + activity["term"]
        for key, ac in activity.groupby("key"):
            d = feats.setdefault(key, {})
            d["activity_mean"] = float(ac["lms_logins"].mean())
            weekly = ac.groupby("week")["lms_logins"].mean()
            d["activity_trend"] = _trend(weekly.index.values, weekly.values)
            d["low_activity_weeks"] = int((weekly <= 0.5).sum())

    # ── Демография/статика ──
    rows = []
    for row in students.itertuples():
        d = feats.get(row.key, {})
        # Возраст на момент периода (год периода из "YYYY-X").
        term_year = int(str(row.term).split("-")[0])
        d["age"] = term_year - int(row.birth_year)
        d["entry_gpa"] = float(row.entry_gpa)
        d["course_year"] = int(row.course_year)
        d["is_paid"] = 1 if str(row.funding_type).strip().lower().startswith("плат") else 0
        d["is_region"] = 1 if str(row.region) == "Область" else 0
        d["is_male"] = 1 if str(row.gender) == "М" else 0
        d.update(
            {
                "student_id": row.student_id,
                "term": row.term,
                "faculty": row.faculty,
                "study_group": row.study_group,
                "program": row.program,
            }
        )
        rows.append(d)

    df = pd.DataFrame(rows)

    # Пропуски (нет оценок/сдач до отсечки) — осмысленные значения по умолчанию.
    defaults = {
        "avg_score": 0.0, "min_score": 0.0, "score_trend": 0.0,
        "fail_rate": 1.0, "key_course_fail_rate": 1.0, "retake_count": 0,
        "course_load": 0, "attendance_rate": 0.0, "attendance_trend": 0.0,
        "absent_weeks": 0, "late_or_missing_rate": 1.0, "missing_count": 0,
        "activity_mean": 0.0, "activity_trend": 0.0, "low_activity_weeks": 0,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
        df[col] = df[col].fillna(val)

    return df


def _labels(tables: dict[str, pd.DataFrame], cutoff: int) -> pd.DataFrame:
    """Строит метки и признак «выбыл до отсечки» для каждого (student, term).

    label = 1, если есть событие expelled с week > cutoff (отчисление позже
    отсечки). already_left = 1, если студент выбыл до/на отсечке (его исключаем
    из скоринга — на момент N его уже нет).
    """
    se = tables["status_events"].copy()
    se["key"] = se["student_id"] + "|" + se["term"]
    out = {}
    for key, g in se.groupby("key"):
        expelled = g[g["event_type"].isin(["expelled", "academic_leave"])]
        already_left = bool((expelled["week"] <= cutoff).any())
        label = int((expelled["week"] > cutoff).any())
        out[key] = {"label": label, "already_left": int(already_left)}
    return pd.DataFrame.from_dict(out, orient="index").reset_index(names="key")


def _build(cutoff: int) -> pd.DataFrame:
    """Загружает данные, считает признаки и присоединяет метки."""
    tables = platonus.load_all()
    feats = _aggregate(tables, cutoff)
    feats["key"] = feats["student_id"] + "|" + feats["term"]
    labels = _labels(tables, cutoff)
    df = feats.merge(labels, on="key", how="left")
    df["label"] = df["label"].fillna(0).astype(int)
    df["already_left"] = df["already_left"].fillna(0).astype(int)
    # Исключаем уже выбывших к отсечке — их не скорим и не учим на них.
    df = df[df["already_left"] == 0].reset_index(drop=True)
    return df


def build_training_frame(cutoff: int | None = None) -> pd.DataFrame:
    """Полная матрица признаков с метками по всем периодам (для обучения/оценки)."""
    cutoff = cutoff if cutoff is not None else config.CUTOFF_WEEK
    return _build(cutoff)


def build_scoring_frame(cutoff: int | None = None, term: str | None = None) -> pd.DataFrame:
    """Матрица признаков для текущих студентов (один период, без метки).

    По умолчанию берётся ПОСЛЕДНИЙ период из данных — те, кого скорим на этой
    неделе. Можно указать конкретный term.
    """
    cutoff = cutoff if cutoff is not None else config.CUTOFF_WEEK
    df = _build(cutoff)
    if term is None:
        # Последний период по сортировке строкового кода "YYYY-X".
        term = sorted(df["term"].unique())[-1]
    return df[df["term"] == term].reset_index(drop=True)


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Выделяет только колонки-признаки в фиксированном порядке."""
    return df[FEATURE_COLUMNS].astype(float)
