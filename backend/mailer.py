# -*- coding: utf-8 -*-
"""
Отправка email (письма должникам о летнем семестре).

Если SMTP не настроен (config.SMTP_HOST пуст) — работает ДЕМО-РЕЖИМ (dry-run):
письма НЕ отправляются. Это защищает от рассылки на фейковые адреса синтетики и
позволяет проверить весь поток без реального почтового сервера.

При настроенном SMTP письма уходят через smtplib (STARTTLS по умолчанию).
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr

import config


def smtp_configured() -> bool:
    """True, если задан SMTP-сервер (иначе — демо-режим)."""
    return bool(config.SMTP_HOST)


def send_email(to: str | None, subject: str, body: str) -> dict:
    """Отправляет одно письмо. Возвращает {status, detail}.

    status: sent | dry-run | error.
    """
    if not to:
        return {"status": "error", "detail": "нет email"}
    if not smtp_configured():
        return {"status": "dry-run", "detail": "SMTP не настроен — демо-режим, письмо не отправлено"}
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_FROM))
        msg["To"] = to
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
            if config.SMTP_USE_TLS:
                server.starttls(context=ssl.create_default_context())
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return {"status": "sent", "detail": "отправлено"}
    except Exception as e:  # noqa: BLE001 — ошибка отправки не должна ронять весь батч
        return {"status": "error", "detail": str(e)}
