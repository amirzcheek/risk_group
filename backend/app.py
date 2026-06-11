# -*- coding: utf-8 -*-
"""
HTTP-сервис (FastAPI) системы «Предиктивная аналитика группы риска».

Назначение: отдавать дашборду эдвайзеров/деканата список студентов группы риска
с объяснением факторов, запускать переобучение и батч-скоринг, а также готовить
тексты уведомлений для рассылки через n8n.

ВАЖНО: список риска чувствителен. Доступ к нему логируется (storage.log_access),
а операции переобучения/скоринга/уведомлений защищены сервисным токеном
(заголовок X-Service-Token). Это вероятностный сигнал для поддержки, не приговор.

Эндпоинты:
  GET  /health             — живость, состояние модели и хранилища.
  GET  /risk               — список группы риска с фильтрами (faculty, group, level).
  GET  /student/{id}       — детальный профиль риска с факторами.
  GET  /summary            — сводка по факультетам/группам.
  POST /score/run          — запустить батч-скоринг (токен).
  POST /train              — переобучить модель (токен).
  POST /notify/run         — для n8n: сгенерировать тексты уведомлений (токен).
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import storage

app = FastAPI(
    title="Группа риска (Early Warning, KNUS)",
    description="Раннее выявление студентов с риском отчисления. Сигнал для "
    "эдвайзеров, решение — за человеком.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Пометка для UI: это вероятностный сигнал, а не приговор.
DISCLAIMER = (
    "Это вероятностный сигнал системы раннего предупреждения, а не приговор. "
    "Решение и любое вмешательство остаются за эдвайзером/деканатом."
)


def _check_token(token: Optional[str]) -> None:
    """Проверяет сервисный токен для защищённых операций."""
    if not config.SERVICE_TOKEN:
        # Токен не задан — разрешаем (режим разработки), но это небезопасно для прода.
        return
    if token != config.SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Неверный или отсутствующий сервисный токен")


# ───────────────────────────── Модели ответов ─────────────────────────────


class NotifyRequest(BaseModel):
    faculty: Optional[str] = None
    group: Optional[str] = None
    level: Optional[str] = None
    limit: int = 100


class TrainRequest(BaseModel):
    cutoff: Optional[int] = None
    top_fraction: Optional[float] = None


class ScoreRequest(BaseModel):
    term: Optional[str] = None
    top_fraction: Optional[float] = None


# ───────────────────────────── Эндпоинты ─────────────────────────────


@app.get("/health")
def health():
    """Живость сервиса, состояние модели и хранилища."""
    import os

    model_ready = os.path.exists(config.MODEL_PATH)
    meta = {}
    if model_ready:
        try:
            import json

            with open(config.MODEL_META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:  # noqa: BLE001
            meta = {}
    last_run = None
    try:
        last_run = storage.latest_run_id()
    except Exception:  # noqa: BLE001
        last_run = None
    return {
        "status": "ok",
        "data_source": config.DATA_SOURCE,
        "storage": storage.backend_name(),
        "model_ready": model_ready,
        "model_trained_at": meta.get("trained_at_utc"),
        "cutoff_week": meta.get("cutoff_week", config.CUTOFF_WEEK),
        "last_score_run": last_run,
        "disclaimer": DISCLAIMER,
    }


@app.get("/risk")
def risk_list(
    faculty: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    level: Optional[str] = Query(None, description="high|medium|low"),
    actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """Список студентов группы риска с фильтрами по факультету/группе/уровню."""
    storage.log_access(actor, "view_risk_list", target=faculty or group or "all",
                       detail={"faculty": faculty, "group": group, "level": level})
    items = storage.get_risk_list(faculty=faculty, group=group, level=level, only_flagged=True)
    return {"count": len(items), "disclaimer": DISCLAIMER, "items": items}


@app.get("/student/{student_id}")
def student_detail(
    student_id: str,
    actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """Детальный профиль риска студента с объяснением факторов."""
    storage.log_access(actor, "view_student", target=student_id)
    item = storage.get_student(student_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Студент не найден в последнем прогоне")
    item["disclaimer"] = DISCLAIMER
    return item


@app.get("/summary")
def summary(actor: Optional[str] = Header(None, alias="X-Actor")):
    """Сводка по факультетам/группам: сколько в зоне риска."""
    storage.log_access(actor, "view_summary", target="all")
    return {"groups": storage.get_summary(), "disclaimer": DISCLAIMER}


@app.post("/score/run")
def score_run(
    req: ScoreRequest,
    token: Optional[str] = Header(None, alias="X-Service-Token"),
):
    """Запустить батч-скоринг (защищено токеном)."""
    _check_token(token)
    import scoring

    try:
        run = scoring.run_scoring(term=req.term, top_fraction=req.top_fraction)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ошибка скоринга: {e}")
    return {"status": "ok", "run": run}


@app.post("/train")
def train_model(
    req: TrainRequest,
    token: Optional[str] = Header(None, alias="X-Service-Token"),
):
    """Переобучить модель (защищено токеном). Возвращает метрики."""
    _check_token(token)
    import train

    try:
        result = train.run_training(cutoff=req.cutoff, top_fraction=req.top_fraction)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ошибка обучения: {e}")
    return {"status": "ok", "meta": result["meta"], "metrics": result["metrics"]}


@app.post("/notify/run")
def notify_run(
    req: NotifyRequest,
    token: Optional[str] = Header(None, alias="X-Service-Token"),
):
    """Для n8n: по флагам сгенерировать тексты уведомлений эдвайзерам.

    Возвращает список сообщений (студент, группа, текст, источник текста).
    Текст оформляет Qwen3; при недоступности LLM — локальная заглушка.
    """
    _check_token(token)
    import llm

    items = storage.get_risk_list(
        faculty=req.faculty, group=req.group, level=req.level, only_flagged=True
    )[: req.limit]
    notifications = []
    for it in items:
        msg = llm.generate_message(it)
        notifications.append(
            {
                "student_id": it["student_id"],
                "faculty": it.get("faculty"),
                "study_group": it.get("study_group"),
                "risk_level": it.get("risk_level"),
                "risk_proba": it.get("risk_proba"),
                "message": msg["text"],
                "text_source": msg["source"],
            }
        )
    return {
        "count": len(notifications),
        "disclaimer": DISCLAIMER,
        "notifications": notifications,
    }
