# -*- coding: utf-8 -*-
"""
Должники и предложение летнего семестра (рассылка деканата).

ОТДЕЛЬНАЯ функция от группы риска: здесь не вероятностный сигнал, а официальный
факт. Студент попадает на летний семестр, если по дисциплине ИТОГОВЫЙ рейтинг
ниже порога (config.SUMMER_PASS_THRESHOLD, по умолчанию 50).

Логика:
  1. Берём оценки текущих студентов за последний период.
  2. По каждой дисциплине считаем итоговый балл (средний по контрольным точкам).
  3. Дисциплина с баллом ниже порога — задолженность.
  4. Набор на летний семестр = эти дисциплины с кредитами ЕКТS.
  5. Сумма к оплате = суммарные кредиты × стоимость кредита (config.CREDIT_COST_SUMMER).
  6. Текст письма собирается по СТРОГОМУ шаблону (без LLM): официальное письмо
     деканата с суммами и юридическими ссылками — генерация недопустима.

Доступ к этим данным — ТОЛЬКО деканат/админ (см. app.py).
"""

from __future__ import annotations

import pandas as pd

import config
import platonus

try:
    from synthetic_data import COURSE_NAMES, COURSE_CREDITS
except Exception:  # noqa: BLE001 — на реальном Платонусе названия/кредиты придут из БД
    COURSE_NAMES, COURSE_CREDITS = {}, {}


def _course_name(code: str) -> str:
    return COURSE_NAMES.get(code, code)


def _course_credits(code: str) -> int:
    # На реальных данных кредиты берутся из учебного плана (esuvo_curriculum / totalmarks).
    return int(COURSE_CREDITS.get(code, 3))


def compute_debtors(term: str | None = None, threshold: float | None = None) -> list[dict]:
    """Список должников последнего периода с дисциплинами-задолженностями и суммой."""
    threshold = threshold if threshold is not None else config.SUMMER_PASS_THRESHOLD
    tables = platonus.load_all()
    students = tables["students"]
    grades = tables["grades"]
    if students.empty or grades.empty:
        return []

    if term is None:
        term = sorted(students["term"].unique())[-1]
    students = students[students["term"] == term]
    grades = grades[grades["term"] == term]

    # Итоговый балл по дисциплине = средний балл по контрольным точкам за период.
    final = (
        grades.groupby(["student_id", "course_code"])["score"].mean().reset_index()
    )
    failed = final[final["score"] < threshold]
    if failed.empty:
        return []

    # Демографию/контакты берём из карточки студента.
    info = students.drop_duplicates("student_id").set_index("student_id")

    debtors = []
    for sid, g in failed.groupby("student_id"):
        if sid not in info.index:
            continue
        row = info.loc[sid]
        disciplines = []
        total_credits = 0
        for r in g.itertuples():
            cr = _course_credits(r.course_code)
            total_credits += cr
            disciplines.append(
                {
                    "code": r.course_code,
                    "name": _course_name(r.course_code),
                    "credits": cr,
                    "mark": round(float(r.score), 1),
                }
            )
        disciplines.sort(key=lambda d: d["mark"])  # сначала самые провальные
        cost = total_credits * config.CREDIT_COST_SUMMER
        debtors.append(
            {
                "student_id": sid,
                "fio": row.get("fio", sid),
                "email": row.get("email"),
                "faculty": row.get("faculty"),
                "study_group": row.get("study_group"),
                "term": term,
                "disciplines": disciplines,
                "total_credits": total_credits,
                "credit_cost": config.CREDIT_COST_SUMMER,
                "amount_due": cost,
            }
        )
    debtors.sort(key=lambda d: d["amount_due"], reverse=True)
    return debtors


def _fmt_kzt(value: int) -> str:
    """Форматирует сумму в тенге с разделителями тысяч."""
    return f"{value:,}".replace(",", " ") + " тенге"


def render_email(debtor: dict) -> dict:
    """Собирает письмо по строгому шаблону деканата (без LLM)."""
    debts = "\n".join(
        f"  • {d['name']} — задолженность (итоговый балл {d['mark']})"
        for d in debtor["disciplines"]
    )
    offer = "\n".join(
        f"  • {d['name']} — {d['credits']} кредитов ЕКТS"
        for d in debtor["disciplines"]
    )
    body = (
        f"Уважаемый(ая) {debtor['fio']}!\n\n"
        f"У вас есть задолженность по следующим дисциплинам:\n{debts}\n\n"
        f"Предлагаем вам пройти летний семестр следующим набором дисциплин:\n{offer}\n\n"
        f"Стоимость одного кредита обучения в летнем семестре: "
        f"{_fmt_kzt(debtor['credit_cost'])}.\n"
        f"К оплате: {_fmt_kzt(debtor['amount_due'])} "
        f"({debtor['total_credits']} кредитов × {_fmt_kzt(debtor['credit_cost'])}).\n"
        f"Сохраните квитанцию об оплате.\n\n"
        f"После оплаты перейдите по ссылке для подачи заявления на летний семестр (EDMS):\n"
        f"{config.EDMS_APPLICATION_URL}\n\n"
        f"Для подачи заявления необходима ЭЦП. Если её нет — получите по ссылке:\n"
        f"{config.ECP_INFO_URL}\n\n"
        f"С уважением,\nДеканат КНУС"
    )
    subject = f"Летний семестр: погашение задолженностей ({debtor['total_credits']} кр.)"
    return {
        "student_id": debtor["student_id"],
        "fio": debtor["fio"],
        "email": debtor["email"],
        "subject": subject,
        "body": body,
        "amount_due": debtor["amount_due"],
        "total_credits": debtor["total_credits"],
    }


def build_notifications(term: str | None = None, threshold: float | None = None) -> list[dict]:
    """Готовые письма для рассылки (n8n)."""
    return [render_email(d) for d in compute_debtors(term=term, threshold=threshold)]
