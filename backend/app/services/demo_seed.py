"""داده نمونه دمو — اجرای کامل خط تولید واقعی سامانه.

این اسکریپت همه چیز را با سرویس‌های واقعی می‌سازد (نه داده خام):
  کاربران → درس → ورود سرفصل → تأیید → مفاهیم → منابع → تولید محتوا →
  انتشار → بانک سؤال → آزمون → پاسخ دانشجو → تسلط → برنامه مطالعه → گفتگو

همان خطی که scripts/seed_demo.py اجرا می‌کند، برای دو مصرف:
  ۱) خط فرمان:  python scripts/seed_demo.py   (پس از scripts/init_db.py)
  ۲) بوت‌استرپ خودکار نسخهٔ پرتیبل (app/core/bootstrap.py) وقتی دیتابیس خالی است.
"""
import sys

# چاپ فارسی روی کنسول‌های cp1252/cp1256 ویندوز (CI و cmd) بدون کرش —
# ریشهٔ خطای UnicodeEncodeError در گام بذر CI روی رانر ویندوز
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from app.core.database import SessionLocal  # noqa: E402
from app.core.jobs import add_step, succeed_job  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.models.assessment import Assessment, Attempt, Response  # noqa: E402
from app.models.collaboration import StudentCreation  # noqa: E402
from app.models.content import ContentDocument, ContentVersion  # noqa: E402
from app.models.courses import Course, CourseOffering, Enrollment  # noqa: E402
from app.models.identity import CourseRole, User  # noqa: E402
from app.models.ops import JobRun  # noqa: E402
from app.models.questions import Question, QuestionVersion  # noqa: E402
from app.models.resources import Resource, ResourcePermission  # noqa: E402
from app.models.syllabus import SyllabusTopic, SyllabusVersion  # noqa: E402
from app.models.tutor import TutorSession  # noqa: E402
from app.services import (assessment_service, collaboration_service,  # noqa: E402
                          concept_service, learning_service, planning_service,
                          question_service, rag, tutor_service)
from app.services.content_service import (create_document, generate_content,  # noqa: E402
                                          propose_plan, confirm_plan, publish_version,
                                          review_version)
from app.services.syllabus_service import approve_version, import_from_source  # noqa: E402
from app.workers.runner import handle_syllabus_import  # noqa: E402

SYLLABUS_TEXT = """
درس: ریاضیات عمومی ۱ — کد MATH101 — مقطع کارشناسی مهندسی — ۳ واحد
مرجع تصویب: شورای آموزشی گروه ریاضی، نیم‌سال جاری

فصل ۱: مقدمه و توابع
1.1 بازنگری مجموعه‌ها و اعداد حقیقی
1.2 مفهوم تابع، دامنه و برد
1.3 ترکیب توابع و توابع معکوس

فصل ۲: حد و پیوستگی
2.1 شهود و تعریف حد
2.2 قوانین حد و فرم‌های نامعین
2.3 پیوستگی تابع در نقطه و بازه

فصل ۳: مشتق و کاربردها
3.1 مفهوم نرخ تغییر و شیب خط مماس
3.2 تعریف حدی مشتق
3.3 قواعد مشتق‌گیری شامل قاعده زنجیره‌ای
3.4 کاربردهای مشتق در تحلیل تابع

اهداف یادگیری:
- محاسبه حد توابع با استفاده از قوانین حد
- تفسیر مشتق به‌عنوان نرخ تغییر و شیب خط مماس
- محاسبه مشتق با قواعد مشتق‌گیری و قاعده زنجیره‌ای
- تحلیل رفتار تابع با استفاده از مشتق
"""

RESOURCE_TEXTS = {
    "کتاب درسی — فصل حد و مشتق": (
        "حد توابع: مفهوم حد پایه‌ی پیوستگی و مشتق است. حد یک تابع در نقطه a، مقداری است که "
        "خروجی تابع با نزدیک شدن ورودی به a به آن میل می‌کند، مستقل از مقدار خود تابع در آن نقطه.\n\n"
        "مشتق: مشتق تابع f در نقطه x، حد نسبت تغییرات تابع به تغییرات ورودی است؛ یعنی نرخ تغییر "
        "لحظه‌ای. مشتق برابر شیب خط مماس بر منحنی در آن نقطه است و با تعریف حدی f'(x) محاسبه می‌شود.\n\n"
        "قاعده زنجیره‌ای: برای ترکیب توابع، مشتق خارجی در مشتق داخلی ضرب می‌شود. این قاعده پرکاربردترین "
        "قاعده مشتق‌گیری در مسائل مهندسی است.\n\n"
        "پیوستگی: تابع در نقطه پیوسته است اگر حد چپ و راست برابر و برابر مقدار تابع باشد. هر تابع "
        "مشتق‌پذیر در نقطه، پیوسته است؛ عکس آن صادق نیست."
    ),
    "جزوه استاد — مثال‌های حل‌شده": (
        "مثال ۱: برای f(x)=x^2 در نقطه x=2، تعریف حدی مشتق را اعمال می‌کنیم؛"
        " نتیجه f'(2)=4 است و شیب خط مماس همان 4 است.\n\n"
        "مثال ۲: نرخ تغییر هزینه تولید؛ اگر C(x) هزینه کل باشد، C'(x) هزینه نهایی است و مبنای تصمیم اقتصادی.\n\n"
        "بدفهمی رایج: بسیاری دانشجویان مشتق را «شیب خط واصل بین دو نقطه» می‌گیرند؛ این اشتباه است؛"
        " مشتق شیب مماس در یک نقطه (حد لحظه‌ای) است نه شیب خط بین دو نقطه."
    ),
    "کلید امتحان میان‌ترم (محرمانه)": (
        "کلید امتحان میان‌ترم — پاسخ سؤال ۱: حد برابر 3 است. پاسخ سؤال ۲: مشتق در x=1 برابر 2 است. "
        "این سند محرمانه است و فقط برای تصحیح رسمی استفاده می‌شود."
    ),
}


def run_job_sync(db, kind: str, payload: dict, user) -> JobRun:
    job = JobRun(kind=kind, payload=payload, created_by=user.id, status="RUNNING")
    db.add(job)
    db.flush()
    from app.workers.runner import get_handler

    handler = get_handler(kind)
    handler(db, job)
    if job.status == "RUNNING":
        succeed_job(db, job)
    return job


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        if db.query(Course).filter(Course.code == "MATH101").first():
            print("داده دمو از قبل موجود است؛ اجرا نشد.")
            return

        # ---------- کاربران ----------
        def mk_user(username, full_name, role):
            u = User(username=username, full_name=full_name,
                     password_hash=hash_password("Pass1234!"), role=role)
            db.add(u)
            db.flush()
            return u

        prof = mk_user("prof.rezaei", "دکتر مریم رضایی", Role.PROFESSOR.value)
        ta = mk_user("ta.karimi", "علی کریمی", Role.STUDENT.value)
        st1 = mk_user("student.sara", "سارا احمدی", Role.STUDENT.value)
        st2 = mk_user("student.amir", "امیر محمدی", Role.STUDENT.value)
        edu = mk_user("edu.admin", "مدیر آموزشی گروه", Role.EDUCATION_ADMIN.value)
        quality = mk_user("quality.expert", "کارشناس کیفیت محتوا", Role.QUALITY_REVIEWER.value)
        tech = mk_user("tech.admin", "مدیر فنی", Role.TECH_ADMIN.value)
        db.flush()

        # ---------- درس و ارائه ----------
        course = Course(code="MATH101", title="ریاضیات عمومی ۱", department="گروه ریاضی",
                        degree_level="کارشناسی", field_of_study="مهندسی", credits=3,
                        term="نیم‌سال جاری", description="درس پایه ریاضی برای دانشجویان مهندسی",
                        created_by=prof.id)
        db.add(course)
        db.flush()
        offering = CourseOffering(course_id=course.id, term="نیم‌سال جاری", professor_id=prof.id)
        db.add(offering)
        db.flush()
        for role, u in ((Role.PROFESSOR, prof), (Role.ASSISTANT, ta), (Role.GROUP_ADMIN, edu)):
            db.add(CourseRole(course_id=course.id, user_id=u.id, role=role.value, granted_by=prof.id))
        for st in (st1, st2):
            db.add(Enrollment(offering_id=offering.id, student_id=st.id))
        db.flush()

        # ---------- ورود سرفصل (خط واقعی) ----------
        job = run_job_sync(db, "syllabus_import",
                           {"course_id": str(course.id), "text": SYLLABUS_TEXT,
                            "source_kind": "TEXT"}, prof)
        sv_id = job.result["syllabus_version_id"]
        sv = db.get(SyllabusVersion, sv_id)
        print(f"syllabus imported: v{sv.version_number} status={sv.status} ambiguous={bool(sv.ambiguous_notes)}")
        sv = approve_version(db, sv, prof, "تأیید هیئت مؤلفان")
        print(f"syllabus approved: v{sv.version_number}")

        # ---------- مفاهیم گراف ----------
        topics = {t.title: t for t in db.query(SyllabusTopic)
                  .filter(SyllabusTopic.syllabus_version_id == sv.id).all()}

        def topic(title_part):
            return next(t for k, t in topics.items() if title_part in k)

        c_limit = concept_service.create_concept(
            db, course.id, prof, "limit", "حد", "مقداری که خروجی تابع با نزدیک شدن ورودی به نقطه به آن میل می‌کند.",
            topic_ids=[topic("شهود و تعریف حد").id], status="APPROVED",
            misconceptions=[{"title": "حد یعنی مقدار تابع در آن نقطه", "correction_hint": "حد به رفتار اطراف نقطه مربوط است، نه مقدار خود نقطه."}])
        c_continuity = concept_service.create_concept(
            db, course.id, prof, "continuity", "پیوستگی",
            "تابع در نقطه پیوسته است اگر حد چپ و راست برابر مقدار تابع باشد.",
            topic_ids=[topic("پیوستگی تابع").id], prerequisite_ids=[c_limit.id], status="APPROVED")
        c_derivative = concept_service.create_concept(
            db, course.id, prof, "derivative", "مشتق",
            "مشتق، حد نسبت تغییرات تابع به تغییرات ورودی است؛ نرخ تغییر لحظه‌ای و شیب خط مماس.",
            topic_ids=[topic("تعریف حدی مشتق").id],
            prerequisite_ids=[c_limit.id, c_continuity.id], status="APPROVED",
            misconceptions=[{"title": "مشتق شیب خط واصل بین دو نقطه است",
                             "correction_hint": "مشتق شیب مماس در یک نقطه است (حد لحظه‌ای)؛ خط واصل میانگین دو نقطه است."}])
        c_chain = concept_service.create_concept(
            db, course.id, prof, "chain_rule", "قاعده زنجیره‌ای",
            "برای ترکیب توابع، مشتق خارجی در مشتق داخلی ضرب می‌شود.",
            topic_ids=[topic("قاعده زنجیره‌ای").id], prerequisite_ids=[c_derivative.id], status="APPROVED")
        concept_service.add_relation(db, prof, c_derivative, c_chain, "APPLIED_IN")
        print("concepts: 4 created (limit, continuity, derivative, chain_rule)")

        # ---------- منابع و قطعه‌بندی RAG ----------
        resources = []
        for title, text in RESOURCE_TEXTS.items():
            res = Resource(
                course_id=course.id, title=title,
                kind="EXAM_KEY" if "کلید" in title else "TEXTBOOK",
                language="FA", license="مالکیت گروه", uploaded_by=prof.id,
                contains_exam_material=("کلید" in title),
            )
            db.add(res)
            db.flush()
            rag.index_resource_text(db, res, text)
            db.add(ResourcePermission(resource_id=res.id, course_id=course.id))
            resources.append(res)
        db.flush()
        print(f"resources: {len(resources)} (کلید امتحان علامت‌گذاری شد و از RAG حذف می‌شود)")

        # ---------- استودیو: تولید محتوا (خط واقعی) ----------
        doc = create_document(db, prof, {
            "course_id": str(course.id), "syllabus_version_id": str(sv.id),
            "title": "آموزش مفهوم مشتق",
            "goal": "CONCEPT_TEACHING", "scope": {"concept_ids": [str(c_derivative.id), str(c_chain.id)]},
            "audience_level": "کارشناسی سال اول", "duration_minutes": 45,
            "language": "FA", "style": "STEPWISE",
            "components": ["definition", "example", "exercise", "formula", "summary", "references"],
            "source_resource_ids": [str(r.id) for r in resources[:2]],
        })
        plan = propose_plan(db, doc, prof)
        confirm_plan(db, plan, prof)
        version = generate_content(db, doc, plan, prof)
        qc = version.qc_report or {}
        print(f"content generated: v{version.version_number} blocks="
              f"{len((version.structured_content or {}).get('blocks', []))} qc={qc.get('overall')} "
              f"coverage={qc.get('coverage_ratio')}")
        version = review_version(db, version, prof, "APPROVE", "بازبینی علمی انجام شد")
        version = publish_version(db, version, prof)
        print("content published")

        # ---------- بانک سؤال (خط واقعی) ----------
        questions = question_service.generate_questions(db, prof, {
            "course_id": str(course.id), "syllabus_version_id": str(sv.id),
            "concept_ids": [str(c.id) for c in (c_limit, c_derivative, c_chain)],
            "types": ["MCQ", "TRUE_FALSE", "SHORT_ANSWER", "NUMERIC", "ESSAY"],
            "count": 12, "difficulty": "MEDIUM", "usage": "QUIZ",
        })
        approved = 0
        for q in questions:
            question_service.review_question(db, prof, q, "APPROVE")
            approved += 1
        print(f"questions: {len(questions)} generated, {approved} approved")

        # ---------- آزمون و تلاش دانشجو ----------
        assessment = assessment_service.create_assessment(db, prof, {
            "course_id": str(course.id), "offering_id": str(offering.id),
            "title": "کوییز مشتق و قواعد آن", "kind": "QUIZ", "mode": "FIXED",
            "blueprint": {"sections": [
                {"concept_ids": [str(c_limit.id), str(c_derivative.id)], "count": 3, "difficulty": "MEDIUM"},
                {"concept_ids": [str(c_chain.id)], "count": 1, "difficulty": None},
            ]},
            "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": True},
        })
        attempt = assessment_service.start_attempt(db, assessment, st1)
        qv_ids = list(attempt.question_version_ids or [])
        print(f"attempt started for سارا: {len(qv_ids)} questions")
        answers = {}
        for i, qv_id in enumerate(qv_ids):
            qv = db.get(QuestionVersion, qv_id)
            q = db.get(Question, qv.question_id)
            if q.type in ("MCQ", "MULTI_SELECT", "TRUE_FALSE"):
                # پاسخ صحیح برای ۲ سؤال اول، نادرست برای بقیه (شبیه‌سازی ضعف)
                correct = qv.answer.get("correct")
                if i < 2:
                    sel = correct[0] if isinstance(correct, list) else correct
                    ans = {"selected": [sel] if isinstance(correct, list) else sel}
                else:
                    opts = qv.options or []
                    wrong = next((o["key"] for o in opts
                                  if o["key"] not in (correct or []) and (not isinstance(correct, list) or o["key"] != correct[0])), None)
                    ans = {"selected": [wrong] if isinstance(correct, list) else wrong}
            elif q.type == "NUMERIC":
                base = float(qv.answer.get("value", 0))
                ans = {"value": base + (0 if i < 2 else base * 0.5), "unit": qv.answer.get("unit", "")}
            else:
                ans = {"text": ("تعریف مشتق، حد نسبت تغییرات تابع به تغییرات ورودی است و نرخ تغییر لحظه‌ای را نشان می‌دهد."
                                if i < 2 else "نمی‌دانم")}
            resp = assessment_service.record_response(db, attempt, qv, ans,
                                                      time_spent_ms=45000 + i * 15000,
                                                      hint_used=(i == 3))
            answers[qv_id] = resp
        result = assessment_service.finish_attempt(db, attempt)
        db.commit()
        print(f"attempt finished: score={result['score']}/{result['max_score']} pending={result['pending_count']}")

        # ---------- تمرین تطبیقی سارا (شواهد بیشتر برای تسلط) ----------
        practice = assessment_service.create_assessment(db, prof, {
            "course_id": str(course.id), "offering_id": str(offering.id),
            "title": "تمرین تطبیقی حد و مشتق", "kind": "PRACTICE", "mode": "ADAPTIVE_PRACTICE",
            "blueprint": {"sections": [{"concept_ids": [str(c.id) for c in (c_limit, c_continuity, c_derivative, c_chain)], "count": 12}]},
            "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": True},
        })
        attempt2 = assessment_service.start_attempt(db, practice, st1)
        answered_correct = 0
        for _ in range(15):
            qv_ids2 = attempt2.question_version_ids or []
            if not qv_ids2:
                break
            qv = db.get(QuestionVersion, qv_ids2[-1])
            q = db.get(Question, qv.question_id)
            correct = qv.answer.get("correct")
            if q.type in ("MCQ", "MULTI_SELECT", "TRUE_FALSE"):
                sel = correct[0] if isinstance(correct, list) else correct
                ans = {"selected": [sel] if isinstance(correct, list) else sel}
                answered_correct += 1
            elif q.type == "NUMERIC":
                ans = {"value": float(qv.answer.get("value", 0)), "unit": qv.answer.get("unit", "")}
            elif q.type == "SHORT_ANSWER":
                ans = {"text": qv.answer.get("accepted", [""])[0] if qv.answer.get("accepted") else "تعریف حد"}
            else:
                ans = {"text": (qv.answer.get("reference") or "پاسخ مرجع")[:120]}
            assessment_service.record_response(db, attempt2, qv, ans, time_spent_ms=30000)
            db.commit()
            if assessment_service.advance_adaptive(db, attempt2) is None:
                break
        r2 = assessment_service.finish_attempt(db, attempt2)
        db.commit()
        print(f"adaptive practice (سارا): {r2['score']}/{r2['max_score']} correct")

        # ---------- تمرین ثابت امیر با پاسخ‌های ضعیف ----------
        practice2 = assessment_service.create_assessment(db, prof, {
            "course_id": str(course.id), "offering_id": str(offering.id),
            "title": "تمرین مشتق", "kind": "PRACTICE", "mode": "FIXED",
            "blueprint": {"sections": [
                {"concept_ids": [str(c_limit.id), str(c_derivative.id)], "count": 4, "difficulty": None},
            ]},
            "policy": {"feedback": "IMMEDIATE", "allow_hint": False, "shuffle": False},
        })
        attempt3 = assessment_service.start_attempt(db, practice2, st2)
        for qv_id in (attempt3.question_version_ids or []):
            qv = db.get(QuestionVersion, qv_id)
            q = db.get(Question, qv.question_id)
            correct = qv.answer.get("correct")
            if q.type in ("MCQ", "MULTI_SELECT", "TRUE_FALSE"):
                opts = qv.options or []
                wrong = next((o["key"] for o in opts if o["key"] not in (correct or [])), "A")
                ans = {"selected": [wrong] if isinstance(correct, list) else wrong}
            elif q.type == "NUMERIC":
                ans = {"value": float(qv.answer.get("value", 0)) * 2}
            else:
                ans = {"text": "نمی‌دانم"}
            assessment_service.record_response(db, attempt3, qv, ans, time_spent_ms=150000)
        r3 = assessment_service.finish_attempt(db, attempt3)
        db.commit()
        print(f"practice (امیر، ضعیف): {r3['score']}/{r3['max_score']}")

        # ---------- پاسخ تشریحی + پیشنهاد AI + تأیید استاد (AC-10) ----------
        essay_assessment = assessment_service.create_assessment(db, prof, {
            "course_id": str(course.id), "offering_id": str(offering.id),
            "title": "تمرین تشریحی مشتق", "kind": "PRACTICE", "mode": "FIXED",
            "blueprint": {"sections": [{"concept_ids": [str(c_derivative.id)], "count": 3, "difficulty": "HARD"}]},
            "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": False},
        })
        attempt4 = assessment_service.start_attempt(db, essay_assessment, st1)
        for qv_id in (attempt4.question_version_ids or []):
            qv = db.get(QuestionVersion, qv_id)
            q = db.get(Question, qv.question_id)
            if q.type in ("ESSAY", "CASE"):
                ans = {"text": "مشتق یعنی نرخ تغییر لحظه‌ای تابع و برابر شیب خط مماس است. "
                               "با تعریف حدی f'(x)=lim (f(x+h)-f(x))/h محاسبه می‌شود. "
                               "مثلاً برای s(t)=t^2 سرعت لحظه‌ای v(t)=2t است. "}
                resp = assessment_service.record_response(db, attempt4, qv, ans, time_spent_ms=180000)
            else:
                ans = {"selected": (qv.answer.get("correct") or ["A"])[0], }
                if not isinstance(ans["selected"], str):
                    ans = {"selected": "A"}
                assessment_service.record_response(db, attempt4, qv, ans)
        assessment_service.finish_attempt(db, attempt4)
        db.commit()
        essay_rows = [r for r in db.query(Response)
                      .filter(Response.attempt_id == attempt4.id).all()
                      if r.grading == "AI_SUGGESTED"]
        if essay_rows:
            from app.models.assessment import Response as RespT
            resp = essay_rows[0]
            fb = resp.ai_feedback or {}
            print(f"essay AI suggestion: {fb.get('total_score')}/{fb.get('max_total')} uncertainty={fb.get('uncertainty')}")
            assessment_service.human_grading_review(db, resp, prof, {
                "scores": fb.get("rubric_scores"),
                "final_score": min(float(fb.get("max_total") or 10), (fb.get("total_score") or 0) + 1),
                "comment": "استدلال خوب؛ مثال مرزی هم اضافه شود. نمره رسمی پس از بازبینی.",
            })
            db.commit()
            print("essay graded by professor (final score set)")

        # ---------- تسلط، تشخیص، مرور و برنامه ----------
        mastery = learning_service.recompute_mastery(db, st1.id, course.id)
        statuses = {str(m.concept_id): m.status for m in mastery}
        print(f"mastery: {[f'{s}' for s in statuses.values()]}")
        diag = learning_service.build_diagnostics(db, st1.id, course.id)
        db.commit()
        print(f"diagnostics: {[(d['hypothesis_type']) for d in diag]}")
        plan = planning_service.generate_study_plan(db, st1, str(course.id),
                                                    {"weekly_hours": 6, "goals": "آمادگی میان‌ترم"})
        db.commit()
        print(f"study plan: {plan.rationale_summary[:80]}…")

        # ---------- استاد هوشمند ----------
        session = tutor_service.create_session(db, st1, str(course.id), "LEARNING")
        msg = tutor_service.answer(db, session, "مشتق دقیقاً چیست و چه تفاوتی با حد دارد؟")
        db.commit()
        print(f"tutor answered: {msg.content[:60]}… citations={len(msg.citations or [])}")

        # ---------- مشارکت دانشجو ----------
        creation = collaboration_service.create_creation(db, st1, str(course.id), {
            "activity_type": "EXPLANATION",
            "concept_id": str(c_derivative.id),
            "content": {"title": "توضیح من: مشتق", "body":
                        "مشتق یعنی نرخ تغییر لحظه‌ای تابع؛ مثل سرعت لحظه‌ای خودرو. "
                        "با تعریف حدی محاسبه می‌شود و با شیب خط مماس برابر است. "
                        "مثال: اگر موقعیت s(t)=t^2 باشد، سرعت v(t)=2t است و در t=3 برابر 6 می‌شود."},
        })
        collaboration_service.submit_creation(db, creation, st1)
        db.commit()
        print(f"student creation: {creation.status}")

        db.commit()
        print("\n=== DEMO READY ===")
        print("کاربران (رمز همه: Pass1234!):")
        print("  prof.rezaei (استاد) | ta.karimi (دستیار) | student.sara / student.amir (دانشجو)")
        print("  edu.admin (مدیر آموزشی) | quality.expert (کیفیت) | tech.admin (مدیر فنی)")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
