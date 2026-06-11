# -*- coding: utf-8 -*-
"""
Слой абстракции доступа к данным (Платонус / синтетика).

Единый интерфейс DataSource отдаёт «сырые» таблицы (студенты, оценки,
посещаемость, сдачи, активность, события статуса) в виде DataFrame. Дальше с
ними работает features.py — ему всё равно, откуда пришли данные.

Реализации:
  * PlatonusSource  — выполняет SQL из data_queries.yaml в MySQL Платонуса
    (строго read-only) по каждому учебному периоду и склеивает результаты.
  * SyntheticSource — читает заранее сгенерированные CSV из backend/data/raw.

Выбор источника — через переменную окружения DATA_SOURCE (см. config.py).
"""

from __future__ import annotations

import os
from typing import Protocol

import pandas as pd

import config

# Имена «логических» таблиц == ключи в data_queries.yaml.
TABLES = ["students", "grades", "attendance", "submissions", "activity", "status_events"]


class DataSource(Protocol):
    """Контракт источника данных: метод на каждую логическую таблицу."""

    def students(self) -> pd.DataFrame: ...
    def grades(self) -> pd.DataFrame: ...
    def attendance(self) -> pd.DataFrame: ...
    def submissions(self) -> pd.DataFrame: ...
    def activity(self) -> pd.DataFrame: ...
    def status_events(self) -> pd.DataFrame: ...


# ───────────────────────────── Синтетический источник ─────────────────────────────


class SyntheticSource:
    """Читает синтетические CSV из каталога config.SYNTHETIC_DIR."""

    def __init__(self, directory: str | None = None):
        self.dir = directory or config.SYNTHETIC_DIR

    def _read(self, name: str) -> pd.DataFrame:
        path = os.path.join(self.dir, f"{name}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Нет файла {path}. Сгенерируйте синтетику: python synthetic_data.py"
            )
        return pd.read_csv(path)

    def students(self):
        return self._read("students")

    def grades(self):
        return self._read("grades")

    def attendance(self):
        return self._read("attendance")

    def submissions(self):
        return self._read("submissions")

    def activity(self):
        return self._read("activity")

    def status_events(self):
        return self._read("status_events")


# ───────────────────────────── Источник Платонуса (MySQL) ─────────────────────────────


class PlatonusSource:
    """Выполняет SQL из data_queries.yaml в MySQL Платонуса (read-only).

    Для каждого логического запроса подставляет параметр :term по списку
    учебных периодов TERMS и склеивает результаты в одну таблицу. Реальные
    имена таблиц/полей берутся ровно из data_queries.yaml — код их не знает.
    """

    def __init__(self, terms: list[str] | None = None):
        import yaml  # локальный импорт — нужен только в режиме Платонуса

        with open(config.DATA_QUERIES_PATH, "r", encoding="utf-8") as f:
            self.queries: dict[str, str] = yaml.safe_load(f)

        # Периоды, которые выгружаем. По умолчанию — те же, что в синтетике,
        # но в проде задайте свой список через переменную PLATONUS_TERMS.
        env_terms = os.getenv("PLATONUS_TERMS", "")
        if terms is not None:
            self.terms = terms
        elif env_terms:
            self.terms = [t.strip() for t in env_terms.split(",") if t.strip()]
        else:
            from synthetic_data import TERMS as _T
            self.terms = list(_T)

    def _connect(self):
        import mysql.connector  # локальный импорт — зависимость нужна только тут

        return mysql.connector.connect(
            host=config.PLATONUS_HOST,
            port=config.PLATONUS_PORT,
            database=config.PLATONUS_DB,
            user=config.PLATONUS_USER,
            password=config.PLATONUS_PASSWORD,
            # Доступ только на чтение — транзакции не открываем.
            autocommit=True,
        )

    def _run(self, name: str) -> pd.DataFrame:
        sql_template = self.queries[name]
        frames = []
        conn = self._connect()
        try:
            for term in self.terms:
                # :term — единственный подставляемый параметр (см. data_queries.yaml).
                sql = sql_template.replace(":term", "%(term)s")
                frames.append(pd.read_sql(sql, conn, params={"term": term}))
        finally:
            conn.close()
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def students(self):
        return self._run("students")

    def grades(self):
        return self._run("grades")

    def attendance(self):
        return self._run("attendance")

    def submissions(self):
        return self._run("submissions")

    def activity(self):
        return self._run("activity")

    def status_events(self):
        return self._run("status_events")


def get_source() -> DataSource:
    """Возвращает источник данных согласно DATA_SOURCE."""
    if config.DATA_SOURCE == "platonus":
        return PlatonusSource()
    return SyntheticSource()


def load_all(source: DataSource | None = None) -> dict[str, pd.DataFrame]:
    """Загружает все логические таблицы из источника в словарь."""
    src = source or get_source()
    return {
        "students": src.students(),
        "grades": src.grades(),
        "attendance": src.attendance(),
        "submissions": src.submissions(),
        "activity": src.activity(),
        "status_events": src.status_events(),
    }
