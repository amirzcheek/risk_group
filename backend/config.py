# -*- coding: utf-8 -*-
"""
Конфигурация сервиса «Предиктивная аналитика группы риска» (Early Warning).

Все адреса БД, моделей и токены берутся ТОЛЬКО из переменных окружения
(см. .env.example). Ничего не хардкодим — это требование безопасности: система
работает строго внутри сети вуза, персональные данные не выходят наружу.

Модуль ничего не вызывает на импорте, только читает окружение. Файл .env, если
он лежит рядом, подхватывается через python-dotenv (необязательная зависимость).
"""

import os

# Необязательно подгружаем .env из текущего/родительского каталога, если
# установлен python-dotenv. На проде переменные обычно приходят из окружения
# контейнера, и dotenv просто ничего не делает.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 — dotenv не обязателен.
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))


def _split_csv(value: str) -> list[str]:
    """Разбирает список значений через запятую, убирая пустые элементы."""
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _abs(path: str) -> str:
    """Приводит путь к абсолютному относительно каталога backend/."""
    return path if os.path.isabs(path) else os.path.join(_HERE, path)


# ─────────────────────────── Источник данных (Платонус) ───────────────────────────
# DATA_SOURCE = "synthetic" | "platonus".
#   synthetic — читает сгенерированные CSV из backend/data/raw (демо без Платонуса);
#   platonus  — выполняет SQL из data_queries.yaml в MySQL Платонуса (read-only).
DATA_SOURCE = os.getenv("DATA_SOURCE", "synthetic").strip().lower()

# Подключение к Платонусу (MySQL, доступ ТОЛЬКО на чтение).
PLATONUS_HOST = os.getenv("PLATONUS_HOST", "")
PLATONUS_PORT = int(os.getenv("PLATONUS_PORT", "3306"))
PLATONUS_DB = os.getenv("PLATONUS_DB", "")
PLATONUS_USER = os.getenv("PLATONUS_USER", "")
PLATONUS_PASSWORD = os.getenv("PLATONUS_PASSWORD", "")

# Путь к файлу с SQL-запросами под конкретную инсталляцию Платонуса.
DATA_QUERIES_PATH = _abs(os.getenv("DATA_QUERIES_PATH", "data_queries.yaml"))

# Каталог синтетических CSV (используется при DATA_SOURCE=synthetic).
SYNTHETIC_DIR = _abs(os.getenv("SYNTHETIC_DIR", os.path.join("data", "raw")))


# ─────────────────────────── Хранилище (Postgres / SQLite) ───────────────────────────
# Признаки, прогнозы и журнал доступа храним в Postgres. Если DATABASE_URL не
# задан — включается локальный SQLite-файл (backend/data/risk.db), чтобы весь
# пайплайн работал end-to-end без поднятого Postgres (для разработки и демо).
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = _abs(os.getenv("SQLITE_PATH", os.path.join("data", "risk.db")))


# ─────────────────────────── Артефакт модели ───────────────────────────
# Куда сохраняется обученная модель и её метаданные.
MODEL_DIR = _abs(os.getenv("MODEL_DIR", os.path.join("data", "model")))
MODEL_PATH = os.path.join(MODEL_DIR, "model.txt")          # бустер LightGBM
MODEL_META_PATH = os.path.join(MODEL_DIR, "model_meta.json")  # метаданные обучения


# ─────────────────────────── Параметры риска ───────────────────────────
# Неделя семестра, на состояние которой строятся признаки (точка отсечки).
# Цель — отчисление СТРОГО ПОЗЖЕ этой недели. Так исключается утечка данных.
CUTOFF_WEEK = int(os.getenv("CUTOFF_WEEK", "6"))

# Доля студентов, попадающих в группу риска (топ-X% по вероятности).
# Управляет нагрузкой на эдвайзеров: 0.10 = флаг получают верхние 10%.
RISK_TOP_FRACTION = float(os.getenv("RISK_TOP_FRACTION", "0.10"))

# Пороги уровней риска по вероятности (для подсветки в UI).
RISK_THRESHOLD_HIGH = float(os.getenv("RISK_THRESHOLD_HIGH", "0.60"))
RISK_THRESHOLD_MEDIUM = float(os.getenv("RISK_THRESHOLD_MEDIUM", "0.30"))


# ─────────── LLM для текста уведомлений (Qwen3-14B через OVMS, OpenAI-совместимый API) ───────────
# ВАЖНО: LLM используется ТОЛЬКО для генерации текста уведомлений эдвайзерам.
# На прогноз риска она НЕ влияет. Если адрес не задан — включается заглушка,
# которая собирает текст из факторов локально (пайплайн работает без живого LLM).
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")


# ─────────────────────────── Безопасность и доступ ───────────────────────────
# Токен для защищённых операций (POST /score/run, /train, /notify/run).
# Передаётся в заголовке X-Service-Token.
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")

# Домены, которым разрешён доступ к API из браузера (через серверный прокси фронта).
CORS_ORIGINS = _split_csv(os.getenv("CORS_ORIGINS", "https://ai.knus.edu.kz,http://localhost:3000"))


def using_postgres() -> bool:
    """True, если задан DATABASE_URL (иначе работаем на локальном SQLite)."""
    return bool(DATABASE_URL)
