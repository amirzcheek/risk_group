# -*- coding: utf-8 -*-
"""
Генерация текста уведомлений эдвайзерам (Qwen3-14B через OVMS).

ВАЖНО: LLM используется ТОЛЬКО для оформления человекочитаемого текста «на что
обратить внимание». На прогноз риска она НЕ влияет — риск считает ML-модель.
Текст всегда строится из фактических топ-факторов конкретного студента.

Если LLM не настроен или недоступен — работает ЗАГЛУШКА: текст собирается из
факторов локально по шаблону. Это позволяет прогонять /notify/run без живого LLM.

Тон сообщений выдержан этично: это вероятностный сигнал для внимания и поддержки,
а НЕ приговор. Решение и вмешательство — всегда за человеком (эдвайзером).
"""

from __future__ import annotations

import config

SYSTEM_PROMPT = (
    "Ты помощник деканата. По данным раннего предупребления составь короткое "
    "(2–3 предложения) деловое сообщение для эдвайзера на русском языке. "
    "Сообщение должно: назвать студента и группу; перечислить 2–3 ключевых "
    "фактора внимания простыми словами; предложить мягкий шаг (связаться, "
    "пригласить на разговор). Подчёркивай, что это вероятностный сигнал для "
    "поддержки, а не приговор. Без обвинений, без диагнозов, без персональных "
    "данных кроме имени/группы."
)


def _factors_text(factors: list[dict]) -> str:
    """Человекочитаемый список факторов из объяснения модели."""
    if not factors:
        return "пониженная общая активность"
    parts = [f["description"] for f in factors[:3]]
    return "; ".join(parts)


def _fallback_message(student: dict) -> str:
    """Заглушка: собирает текст уведомления локально, без LLM."""
    name = student.get("student_id", "студент")
    group = student.get("study_group", "")
    level_map = {"high": "высокий", "medium": "средний", "low": "низкий"}
    level = level_map.get(student.get("risk_level", ""), "повышенный")
    factors = _factors_text(student.get("top_factors", []))
    return (
        f"Студент {name} (группа {group}) — {level} сигнал риска по системе раннего "
        f"предупреждения. На что обратить внимание: {factors}. "
        f"Рекомендуем связаться со студентом и предложить поддержку. "
        f"Это вероятностный сигнал, а не окончательное решение — оценка остаётся за вами."
    )


def _user_prompt(student: dict) -> str:
    """Промпт для LLM: подаём факты, просим оформить текст."""
    factors = "\n".join(
        f"- {f['description']} (значение {f.get('value')})"
        for f in student.get("top_factors", [])[:3]
    ) or "- общая активность ниже ожидаемой"
    return (
        f"Студент: {student.get('student_id')}\n"
        f"Группа: {student.get('study_group')}\n"
        f"Факультет: {student.get('faculty')}\n"
        f"Уровень сигнала: {student.get('risk_level')}\n"
        f"Вероятность риска: {student.get('risk_proba')}\n"
        f"Ключевые факторы:\n{factors}\n\n"
        f"Составь сообщение для эдвайзера по правилам из системной инструкции."
    )


def generate_message(student: dict) -> dict:
    """Возвращает {text, source}. source: 'llm' или 'fallback'."""
    if not config.LLM_BASE_URL or not config.LLM_MODEL:
        return {"text": _fallback_message(student), "source": "fallback"}
    try:
        from openai import OpenAI

        client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(student)},
            ],
            temperature=0.4,
            max_tokens=220,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return {"text": _fallback_message(student), "source": "fallback"}
        return {"text": text, "source": "llm"}
    except Exception:  # noqa: BLE001 — недоступность LLM не должна ронять прогон
        return {"text": _fallback_message(student), "source": "fallback"}
