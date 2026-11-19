"""تصحیح پاسخ‌ها (بخش ۷.۲) — هر نوع پاسخ روش اولیه خود را دارد.

- چندگزینه‌ای/درست‌نادرست/چندپاسخی/مرتب‌سازی/تطبیق: تصحیح قطعی
- عددی: محدوده خطا، واحد و قواعد تعریف‌شده
- کوتاه: پاسخ‌های معتبر + بررسی معنایی با نظارت (غیرقطعی)
- تشریحی: روبرک، شواهد و «پیشنهاد نمره» — نمره رسمی طبق سیاست انسانی نهایی می‌شود
- کدنویسی: فقط در Sandbox ایزوله اجرا می‌شود؛ در MVP وضعیت NOT_EXECUTED ثبت می‌شود
"""
import re

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.schemas import EssayGradeOut, ShortAnswerCheckOut


def normalize_persian(text: str) -> str:
    text = (text or "").lower().strip()
    for a, b in (("ي", "ی"), ("ك", "ک"), ("ة", "ه"), ("\u200c", " ")):
        text = text.replace(a, b)
    text = re.sub(r"[.,؛،؟!:]+", " ", text)
    return " ".join(text.split())


def grade_objective(qtype: str, qv, answer) -> tuple[float, dict]:
    """تصحیح قطعی — بازگشت (correctness 0..1, جزئیات)."""
    if qtype in ("MCQ", "MULTI_SELECT", "TRUE_FALSE", "ORDERING", "MATCHING"):
        correct = qv.answer.get("correct")
        if qtype == "TRUE_FALSE":
            ok = 1.0 if str(answer.get("selected", answer)).upper() == str(correct) else 0.0
            return ok, {"expected": correct}
        chosen = answer.get("selected") if isinstance(answer, dict) else answer
        if isinstance(chosen, str):
            chosen = [chosen]
        chosen = set(chosen or [])
        expected = set(correct or [])
        if qtype == "MCQ":
            return (1.0 if chosen == expected else 0.0), {"expected": sorted(expected)}
        # چندپاسخی: نمره نسبی با کسر برای گزینه اشتباه
        hits = len(chosen & expected)
        misses = len(chosen - expected)
        denom = max(1, len(expected))
        return max(0.0, (hits - misses) / denom), {"expected": sorted(expected)}
    if qtype == "NUMERIC":
        try:
            value = float(answer.get("value"))
        except (TypeError, ValueError, AttributeError):
            return 0.0, {"error": "پاسخ عددی نامعتبر"}
        expected = float(qv.answer.get("value"))
        tol = float(qv.answer.get("tolerance", 0.0) or 0.0)
        unit_ok = (not qv.answer.get("unit")) or \
                  normalize_persian(str(answer.get("unit", ""))) == normalize_persian(str(qv.answer["unit"]))
        within = abs(value - expected) <= tol + 1e-9
        if within and unit_ok:
            return 1.0, {"expected": expected}
        # خطای محاسبه‌ای نزدیک — سیگنال کمکی برای تشخیص ریشه
        near = abs(value - expected) <= max(abs(expected) * 0.15, 1.0)
        return 0.0, {"expected": expected, "near_miss": near, "unit_ok": unit_ok}
    return 0.0, {}


def grade_short_answer(db: Session, qv, answer) -> dict:
    """پاسخ کوتاه: پاسخ‌های معتبر + بررسی معنایی غیرقطعی."""
    text = normalize_persian(str(answer.get("text", "")) if isinstance(answer, dict) else str(answer))
    accepted = [normalize_persian(a) for a in (qv.answer.get("accepted") or [])]
    for acc in accepted:
        if acc and (acc in text or text in acc):
            return {"correctness": 1.0, "grading": "AUTO", "details": {"matched": acc}}
    # بررسی معنایی با AI — فقط پیشنهاد، با نظارت استاد
    try:
        gateway = AIGateway(db)
        check: ShortAnswerCheckOut = gateway.run(
            "short_answer_check",
            {"accepted": qv.answer.get("accepted") or [], "student_answer": text},
            schema=ShortAnswerCheckOut,
        )
        return {"correctness": 1.0 if check.correct else 0.0, "grading": "AI_SUGGESTED",
                "details": {"ai_check": check.model_dump(), "non_authoritative": True}}
    except Exception:  # noqa: BLE001 — حالت جایگزین بدون AI: نیاز به بررسی انسانی
        return {"correctness": None, "grading": "PENDING",
                "details": {"note": "بررسی معنایی در دسترس نیست؛ نیازمند بازبینی استاد"}}


def grade_essay(db: Session, qv, answer) -> dict:
    """تشریحی: پیشنهاد نمره بر اساس روبرک با شواهد؛ نمره رسمی با استاد."""
    text = str(answer.get("text", "")) if isinstance(answer, dict) else str(answer or "")
    try:
        gateway = AIGateway(db)
        grade: EssayGradeOut = gateway.run(
            "essay_grading",
            {"question": qv.body, "rubric": qv.rubric or [],
             "reference_answer": qv.answer.get("reference", ""),
             "student_answer": text[:6000]},
            schema=EssayGradeOut,
        )
        data = grade.model_dump()
        data["non_authoritative"] = True
        return {"correctness": None, "grading": "AI_SUGGESTED", "details": data}
    except Exception:  # noqa: BLE001
        return {"correctness": None, "grading": "PENDING",
                "details": {"note": "نمره‌دهی AI در دسترس نیست؛ نیازمند تصحیح استاد"}}


def grade_code(qv, answer) -> dict:
    """کد دانشجو هرگز در فرایند API اجرا نمی‌شود؛ نیازمند Sandbox ایزوله با
    کنترل CPU/حافظه/زمان/شبکه — در استقرار نهایی سرویس جداگانه است."""
    return {"correctness": None, "grading": "NOT_EXECUTED",
            "details": {"note": "اجرای کد نیازمند محیط ایزوله است؛ در این نسخه اجرا نمی‌شود",
                        "received": bool(answer)}}
