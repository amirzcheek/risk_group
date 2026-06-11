# -*- coding: utf-8 -*-
"""
Хранилище признаков, прогнозов и журнала доступа.

Абстракция над БД: если задан DATABASE_URL — работаем с Postgres (psycopg2),
иначе — с локальным SQLite-файлом (backend/data/risk.db). Это позволяет
запустить весь пайплайн end-to-end без поднятого Postgres (разработка/демо),
сохранив тот же интерфейс и ту же логическую схему (см. migrations/001_init.sql).

JSON-поля (features, top_factors, detail) в Postgres хранятся как JSONB, в
SQLite — как TEXT с JSON внутри; чтение всегда возвращает словари/списки.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any

import config


# ───────────────────────────── Соединение ─────────────────────────────


def _is_pg() -> bool:
    return config.using_postgres()


@contextmanager
def _conn():
    if _is_pg():
        import psycopg2

        conn = psycopg2.connect(config.DATABASE_URL)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _ph() -> str:
    """Плейсхолдер параметров: %s для Postgres, ? для SQLite."""
    return "%s" if _is_pg() else "?"


def _dump(obj: Any) -> Any:
    """Сериализация JSON-поля под текущую БД."""
    if _is_pg():
        from psycopg2.extras import Json

        return Json(obj)
    return json.dumps(obj, ensure_ascii=False)


def _load(val: Any) -> Any:
    """Десериализация JSON-поля (SQLite хранит как текст)."""
    if isinstance(val, (dict, list)) or val is None:
        return val
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return val


# ───────────────────────────── Инициализация схемы ─────────────────────────────

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL, term TEXT NOT NULL, cutoff_week INTEGER NOT NULL,
    faculty TEXT, study_group TEXT, program TEXT,
    features TEXT NOT NULL, computed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, term, cutoff_week)
);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL, student_id TEXT NOT NULL, term TEXT NOT NULL,
    faculty TEXT, study_group TEXT, program TEXT,
    risk_proba REAL NOT NULL, risk_level TEXT NOT NULL,
    is_flagged INTEGER NOT NULL DEFAULT 0, top_factors TEXT NOT NULL,
    model_version TEXT, scored_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pred_run ON predictions (run_id);
CREATE INDEX IF NOT EXISTS idx_pred_flag ON predictions (is_flagged);
CREATE TABLE IF NOT EXISTS score_runs (
    run_id TEXT PRIMARY KEY, term TEXT, cutoff_week INTEGER,
    n_students INTEGER, n_flagged INTEGER, threshold REAL, model_version TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT, action TEXT NOT NULL, target TEXT, detail TEXT,
    at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    """Создаёт таблицы. Для Postgres применяет migrations/001_init.sql."""
    with _conn() as conn:
        cur = conn.cursor()
        if _is_pg():
            sql_path = os.path.join(os.path.dirname(__file__), "migrations", "001_init.sql")
            with open(sql_path, "r", encoding="utf-8") as f:
                cur.execute(f.read())
        else:
            cur.executescript(_SQLITE_DDL)


# ───────────────────────────── Запись прогнозов ─────────────────────────────


def save_run(run: dict, rows: list[dict]) -> None:
    """Сохраняет метаданные прогона и строки прогнозов."""
    init_db()
    ph = _ph()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO score_runs (run_id, term, cutoff_week, n_students, n_flagged, "
            f"threshold, model_version) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (run["run_id"], run["term"], run["cutoff_week"], run["n_students"],
             run["n_flagged"], run["threshold"], run["model_version"]),
        )
        for r in rows:
            cur.execute(
                f"INSERT INTO predictions (run_id, student_id, term, faculty, study_group, "
                f"program, risk_proba, risk_level, is_flagged, top_factors, model_version) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
                (run["run_id"], r["student_id"], r["term"], r.get("faculty"),
                 r.get("study_group"), r.get("program"), r["risk_proba"], r["risk_level"],
                 bool(r["is_flagged"]) if _is_pg() else int(r["is_flagged"]),
                 _dump(r["top_factors"]), run["model_version"]),
            )


def latest_run_id(term: str | None = None) -> str | None:
    """Возвращает run_id последнего прогона (опционально по периоду)."""
    ph = _ph()
    with _conn() as conn:
        cur = conn.cursor()
        if term:
            cur.execute(
                f"SELECT run_id FROM score_runs WHERE term={ph} ORDER BY created_at DESC LIMIT 1",
                (term,),
            )
        else:
            cur.execute("SELECT run_id FROM score_runs ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None


# ───────────────────────────── Чтение прогнозов ─────────────────────────────


def _row_to_dict(row) -> dict:
    d = dict(row) if not isinstance(row, dict) else row
    d["top_factors"] = _load(d.get("top_factors"))
    d["is_flagged"] = bool(d.get("is_flagged"))
    return d


def get_risk_list(
    faculty: str | None = None,
    group: str | None = None,
    level: str | None = None,
    only_flagged: bool = True,
    run_id: str | None = None,
) -> list[dict]:
    """Список студентов группы риска последнего прогона с фильтрами."""
    init_db()
    rid = run_id or latest_run_id()
    if rid is None:
        return []
    ph = _ph()
    clauses = [f"run_id={ph}"]
    params: list[Any] = [rid]
    if only_flagged:
        clauses.append("is_flagged=" + ("TRUE" if _is_pg() else "1"))
    if faculty:
        clauses.append(f"faculty={ph}")
        params.append(faculty)
    if group:
        clauses.append(f"study_group={ph}")
        params.append(group)
    if level:
        clauses.append(f"risk_level={ph}")
        params.append(level)
    where = " AND ".join(clauses)
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT student_id, term, faculty, study_group, program, risk_proba, "
            f"risk_level, is_flagged, top_factors, model_version, scored_at "
            f"FROM predictions WHERE {where} ORDER BY risk_proba DESC",
            tuple(params),
        )
        cols = [c[0] for c in cur.description]
        return [_row_to_dict(dict(zip(cols, r))) for r in cur.fetchall()]


def get_student(student_id: str, run_id: str | None = None) -> dict | None:
    """Детальный прогноз по студенту из последнего прогона."""
    init_db()
    rid = run_id or latest_run_id()
    if rid is None:
        return None
    ph = _ph()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT student_id, term, faculty, study_group, program, risk_proba, "
            f"risk_level, is_flagged, top_factors, model_version, scored_at "
            f"FROM predictions WHERE run_id={ph} AND student_id={ph} LIMIT 1",
            (rid, student_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return _row_to_dict(dict(zip(cols, row)))


def get_summary(run_id: str | None = None) -> list[dict]:
    """Сводка по факультетам/группам: сколько в зоне риска."""
    init_db()
    rid = run_id or latest_run_id()
    if rid is None:
        return []
    ph = _ph()
    flag = "TRUE" if _is_pg() else "1"
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT faculty, study_group, COUNT(*) AS total, "
            f"SUM(CASE WHEN is_flagged={flag} THEN 1 ELSE 0 END) AS flagged "
            f"FROM predictions WHERE run_id={ph} GROUP BY faculty, study_group "
            f"ORDER BY flagged DESC, faculty",
            (rid,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ───────────────────────────── Журнал доступа ─────────────────────────────


def log_access(actor: str | None, action: str, target: str | None = None, detail: dict | None = None) -> None:
    """Пишет запись в журнал доступа (кто смотрел список риска)."""
    init_db()
    ph = _ph()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO access_log (actor, action, target, detail) VALUES ({ph},{ph},{ph},{ph})",
            (actor or "unknown", action, target, _dump(detail or {})),
        )


def backend_name() -> str:
    """Человекочитаемое имя активного бэкенда хранилища."""
    return "PostgreSQL" if _is_pg() else f"SQLite ({config.SQLITE_PATH})"
