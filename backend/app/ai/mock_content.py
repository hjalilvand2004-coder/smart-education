"""مولد قطعی (Mock) محتوای آموزشی، سؤال و پاسخ استاد هوشمند.

این ماژول جای «مدل زبانی واقعی» در محیط توسعه/دمو را می‌گیرد و خروجی
ساختاریافته معتبر با همان Schema تولید می‌کند تا کل خط تولید قابل آزمون باشد.
با تنظیم S360_AI_PROVIDER=openai_compat و آدرس مدل واقعی، بدون تغییر منطق
سرویس‌ها مدل اصلی جایگزین می‌شود.
"""
import hashlib

# فرمول‌های نمونه (قالب LaTeX — در HTML با KaTeX و در PDF/PPTX به‌صورت متن ساده)
FORMULAS = {
    "limit": "\\lim_{x \\to a} f(x) = L",
    "derivative": "f'(x) = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}",
    "chain_rule": "(f \\circ g)'(x) = f'(g(x)) \\cdot g'(x)",
    "continuity": "\\lim_{x \\to a^-} f(x) = \\lim_{x \\to a^+} f(x) = f(a)",
}

SCENARIOS = [
    ("فیزیک", "سرعت لحظه‌ای یک خودرو که موقعیت آن با زمان تغییر می‌کند"),
    ("اقتصاد", "نرخ تغییر هزینه کل تولید نسبت به تعداد محصول"),
    ("هندسه", "شیب خط مماس بر منحنی در یک نقطه"),
]


def _hash_int(text: str) -> int:
    return int(hashlib.blake2b(text.encode("utf-8"), digest_size=4).hexdigest(), 16)


def _pick(seq, seed):
    return seq[_hash_int(seed) % len(seq)]


def mock_content_plan(inputs: dict) -> dict:
    concepts = inputs["concepts"]
    objectives = inputs["objectives"]
    duration = inputs.get("duration_minutes") or max(30, 15 * len(concepts))
    per_concept = max(8, duration // max(1, len(concepts)))
    sections = [{"block_type": "heading", "concept_keys": [], "minutes": 2,
                 "notes": "عنوان و معرفی جلسه"}]
    sections.append({"block_type": "text", "concept_keys": [], "minutes": 5,
                     "notes": "معرفی هدف و انگیزه (چرا این مفهوم مهم است؟)"})
    for c in concepts:
        sections.append({"block_type": "definition", "concept_keys": [c["key"]], "minutes": per_concept // 3,
                         "notes": f"تعریف دقیق «{c['name']}» و اجزای آن"})
        sections.append({"block_type": "worked_example", "concept_keys": [c["key"]], "minutes": per_concept // 2,
                         "notes": f"مثال حل‌شده برای «{c['name']}»"})
        if c.get("misconceptions"):
            sections.append({"block_type": "note", "concept_keys": [c["key"]], "minutes": 3,
                             "notes": f"هشدار بدفهمی رایج درباره «{c['name']}»"})
        sections.append({"block_type": "self_check", "concept_keys": [c["key"]], "minutes": per_concept // 6,
                         "notes": f"پرسش خودارزیابی «{c['name']}»"})
    sections.append({"block_type": "summary", "concept_keys": [c["key"] for c in concepts], "minutes": 5,
                     "notes": "جمع‌بندی و اتصال مفاهیم"})
    sections.append({"block_type": "reference", "concept_keys": [], "minutes": 2, "notes": "منابع"})
    return {
        "title": inputs["title"],
        "learning_objectives": [o["statement"] for o in objectives] or
        [f"پس از این جلسه دانشجو بتواند «{c['name']}» را توضیح دهد و در مسئله به‌کار بگیرد." for c in concepts],
        "prerequisites": [p for c in concepts for p in c.get("prerequisites", [])],
        "sections_order": sections,
        "examples": [f"مثال {_pick([s[1] for s in SCENARIOS], c['key'])} برای «{c['name']}»" for c in concepts],
        "timing_summary": f"مجموع زمان برنامه‌ریزی‌شده حدود {duration} دقیقه به‌صورت مرحله‌ای.",
        "assessment_method": "پرسش‌های خودارزیابی درون‌محتوایی + تمرین پایانی بخش؛ ارزیابی رسمی با کوییز نگاشت‌شده به همین مفاهیم.",
    }


def mock_content_generation(inputs: dict) -> dict:
    concepts = inputs["concepts"]
    objectives = inputs["objectives"]
    resources = inputs.get("resources", [])
    style = inputs.get("style", "ACADEMIC")
    components = inputs.get("components") or []
    duration = inputs.get("duration_minutes") or 45
    title = inputs.get("title", "محتوای آموزشی")
    goal_map = {
        "INTRO": "آشنایی کلی با موضوع و جایگاه آن در درس",
        "CONCEPT_TEACHING": "آموزش مفهومی دقیق و قابل به‌کارگیری",
        "PROBLEM_SOLVING": "توانایی حل مسئله با مفاهیم درس",
        "REVIEW": "مرور و تثبیت آموخته‌های قبلی",
        "PRACTICE": "تمرین و ارتقای مهارت",
    }
    blocks: list[dict] = []

    def add(**kw):
        blocks.append(kw)

    add(type="heading", title=title,
        body=f"هدف این بخش: {goal_map.get(inputs.get('goal', 'CONCEPT_TEACHING'))} مطابق سرفصل مصوب درس.")
    add(type="text", title="چرا این موضوع مهم است؟",
        body=(
            "در این بخش، مطابق اهداف یادگیری سرفصل مصوب، مفهوم‌های اصلی را گام‌به‌گام می‌سازیم. "
            + "ابتدا تعریف دقیق هر مفهوم را می‌بینیم، سپس با مثال حل‌شده درک را عمیق می‌کنیم و در پایان "
              "با پرسش‌های خودارزیابی آماده تمرین و ارزیابی می‌شویم."
        ),
        concept_ids=[], source_refs=[r["id"] for r in resources[:1]])

    # پوشش اهداف یادگیری: هر هدف به یک بلوک تعریف/توضیح متصل می‌شود
    for obj in objectives[:4]:
        add(type="note", title=f"هدف یادگیری {obj.get('code', '')}",
            body=obj["statement"])

    for c in concepts:
        cid = c["id"]
        srcs = [r["id"] for r in resources[:2]]
        add(type="definition", title=f"تعریف: {c['name']}",
            body=c.get("description") or f"«{c['name']}» یکی از مفاهیم کلیدی این بخش از درس است که مطابق سرفصل مصوب باید با دقت تعریف و تفکیک شود.",
            concept_ids=[cid], source_refs=srcs)
        if style == "STEPWISE":
            add(type="text", title=f"توضیح مرحله‌به‌مرحله {c['name']}", items=[
                f"گام ۱ — پیش‌نیازها را به‌خاطر بسپار: {', '.join(c.get('prerequisites', []) or ['مفاهیم قبلی درس'])}.",
                f"گام ۲ — تعریف «{c['name']}» را با تعریف دقیقش تطبیق بده.",
                f"گام ۳ — یک مثال ساده را خودت بازسازی کن.",
                f"گام ۴ — در مسئله‌ای واقعی، مکان استفاده از «{c['name']}» را پیدا کن.",
            ], concept_ids=[cid])
        else:
            dom, scen = _pick(SCENARIOS, c["key"])
            add(type="text", title=f"شهود و کاربرد {c['name']}",
                body=(
                    f"برای ساختن شهود، از موقعیتی در {dom} کمک می‌گیریم: {scen}. "
                    f"در چنین موقعیت‌هایی، «{c['name']}» ابزار رسمی توصیف همان پدیده است. "
                    "دقت کن که تعریف رسمی و شهود روزمره باید به هم گره بخورند؛ وگرنه در مسائل غیرعادی دچار خطا می‌شویم."
                ),
                concept_ids=[cid], source_refs=srcs)
        formula = FORMULAS.get(c["key"])
        if formula:
            add(type="formula", title=f"فرمول {c['name']}", formula=formula, concept_ids=[cid])
        if "example" in components or True:
            dom, scen = _pick(SCENARIOS, c["key"] + "ex")
            add(type="worked_example", title=f"مثال حل‌شده: {c['name']}",
                question=f"مسئله ({dom}): {scen} را با استفاده از «{c['name']}» تحلیل و حل کن.",
                steps=[
                    "صورت مسئله را با داده‌های معلوم و مجهول مرتب می‌کنیم.",
                    f"تشخیص می‌دهیم که ابزار مناسب، مفهوم «{c['name']}» است و تعریف آن را می‌نویسیم.",
                    "با اعمال تعریف، حل را گام‌به‌گام پیش می‌بریم و هر گام را تفسیر می‌کنیم.",
                    "نتیجه را بازبینی و با شهود مقایسه می‌کنیم؛ در صورت ناسازگاری، تعریف را دوباره بررسی می‌کنیم.",
                ],
                concept_ids=[cid], source_refs=srcs)
        if c.get("misconceptions"):
            mc = c["misconceptions"][0]
            add(type="note", title="هشدار: بدفهمی رایج",
                body=f"بدفهمی رایج: «{mc['title']}». {mc.get('correction_hint') or 'تعریف دقیق مفهوم را ملاک قرار بده، نه حدس شهودی.'}",
                concept_ids=[cid])
        add(type="self_check", title="خودارزیابی",
            question=f"با کلمات خودت، تعریف «{c['name']}» را بنویس و یک مثال بزن که آن را نشان دهد.",
            answer=f"پاسخ درست باید تعریف دقیق «{c['name']}» را پوشش دهد و مثال باید با تعریف سازگار باشد؛ ضدنمونه هم کمک می‌کند مرز مفهوم را ببینی.",
            explanation="پاسخ خود را با تعریف بلوک تعریف مقایسه کن؛ اگر مثال تو با تعریف نمی‌خواند، بخش شهود را دوباره بخوان.",
            concept_ids=[cid])

    if len(concepts) >= 2:
        add(type="table", title="جمع‌بندی مفاهیم این بخش",
            columns=["مفهوم", "ایده کلیدی", "کاربرد نمونه"],
            rows=[[c["name"], (c.get("description") or "")[:60], _pick([s[1] for s in SCENARIOS], c["key"])]
                  for c in concepts])
    if "exercise" in components or True:
        c0 = concepts[0] if concepts else None
        if c0:
            add(type="exercise", title="تمرین پایانی بخش",
                question=f"یک مسئله از کاربردهای «{c0['name']}» طراحی کن، آن را حل کن و بنویس هر گام حل کدام بخش تعریف را به‌کار برده است.",
                items=[
                    "راهنما: از تعریف دقیق شروع کن، نه از حدس شهودی.",
                    "راهنما: یک ضدنمونه هم بنویس تا مرز مفهوم روشن شود.",
                ],
                concept_ids=[c0["id"]])
    add(type="summary", title="جمع‌بندی",
        body="در این بخش تعریف دقیق مفاهیم را دیدیم، با مثال حل‌شده شهود ساختیم، بدفهمی‌های رایج را شناختیم "
             "و با خودارزیابی آماده تمرین و ارزیابی شدیم. در گام بعد، سؤال‌های تمرینی همین مفاهیم را حل خواهیم کرد.",
        concept_ids=[c["id"] for c in concepts])
    if resources:
        add(type="reference", title="منابع",
            items=[f"{r['title']}" for r in resources] + ["سرفصل مصوب درس — نسخه جاری"],
            source_refs=[r["id"] for r in resources])
    return {"title": title, "blocks": blocks}


def mock_block_regeneration(inputs: dict) -> dict:
    block = dict(inputs["block"])
    instruction = inputs.get("instruction") or "سطح توضیح را دقیق‌تر و مثال را ملموس‌تر کن."
    block["body"] = (
        f"(نسخه بازتولیدشده با دستور: {instruction}) "
        + (block.get("body") or "")
        + " در این بازنگری، تعریف با زبانی دقیق‌تر بازنویسی شده و یک مثال واقعی‌تر برای تقویت شهود اضافه شده است."
    )
    if block.get("type") == "worked_example" and block.get("steps"):
        block["steps"] = list(block["steps"]) + [
            "گام تکمیلی: نتیجه را در یک موقعیت مشابه دیگر هم آزمون کن تا اعتبار حل روشن شود."
        ]
    return {"block": block}


def mock_question_generation(inputs: dict) -> dict:
    concepts = inputs["concepts"]
    types = inputs.get("types") or ["MCQ"]
    usage = inputs.get("usage", "PRACTICE")
    out = []
    rubric = [{"criterion": "دقت مفهومی", "max_score": 5},
              {"criterion": "کامل بودن استدلال", "max_score": 3},
              {"criterion": "وضوح بیان", "max_score": 2}]
    for c in concepts:
        mc = c.get("misconceptions") or []
        wrong = mc[0]["title"] if mc else f"«{c['name']}» با تعریف شهودی روزمره یکسان است"
        prereq = ", ".join(c.get("prerequisites", []) or ["مفاهیم مقدماتی"])
        for t in types:
            if t == "MCQ":
                options = [
                    {"key": "A", "text": c.get("description") or f"تعریف دقیق «{c['name']}» مطابق کتاب درس"},
                    {"key": "B", "text": wrong},
                    {"key": "C", "text": f"همان تعریف مفهوم پیش‌نیاز ({prereq}) با نام جدید"},
                    {"key": "D", "text": f"«{c['name']}» فقط یک نماد است و تعریف مستقلی ندارد"},
                ]
                rot = _hash_int(c["key"] + "mcq") % 4
                options = options[rot:] + options[:rot]
                correct = next(o["key"] for o in options if
                               o["text"] == c.get("description") or
                               (not c.get("description") and o["text"].startswith("تعریف دقیق")))
                out.append({
                    "type": "MCQ",
                    "body": f"کدام گزینه درباره «{c['name']}» درست است؟",
                    "options": options,
                    "answer": {"correct": [correct]},
                    "explanation": f"گزینه درست، تعریف دقیق مطابق منبع است. گزینه «{wrong[:40]}…» همان بدفهمی رایج است؛ "
                                   f"دقت کن «{c['name']}» به پیش‌نیاز ({prereq}) تکیه دارد اما با آن یکی نیست.",
                    "difficulty": _pick(["EASY", "MEDIUM", "MEDIUM", "HARD"], c["key"] + "mcq"),
                    "cognitive_level": "UNDERSTAND",
                    "concept_key": c["key"],
                    "misconception": mc[0]["title"] if mc else None,
                })
            elif t == "TRUE_FALSE":
                out.append({
                    "type": "TRUE_FALSE",
                    "body": f"درست یا نادرست؟ «{wrong}»",
                    "answer": {"correct": "FALSE"},
                    "explanation": f"این جمله نمونه‌ای از بدفهمی رایج درباره «{c['name']}» است و با تعریف دقیق نمی‌خواند.",
                    "difficulty": "EASY",
                    "cognitive_level": "REMEMBER",
                    "concept_key": c["key"],
                    "misconception": mc[0]["title"] if mc else None,
                })
            elif t == "SHORT_ANSWER":
                out.append({
                    "type": "SHORT_ANSWER",
                    "body": f"تعریف «{c['name']}» را در یک تا دو جمله بنویس.",
                    "answer": {"accepted": [c.get("description") or f"تعریف دقیق {c['name']}"]},
                    "explanation": "پاسخ باید اجزای اصلی تعریف را پوشش دهد؛ مثال‌های مرزی هم امتیاز توضیح می‌دهند.",
                    "difficulty": "MEDIUM",
                    "cognitive_level": "UNDERSTAND",
                    "concept_key": c["key"],
                })
            elif t == "NUMERIC":
                base = 10 + (_hash_int(c["key"] + "num") % 90) / 2
                out.append({
                    "type": "NUMERIC",
                    "body": f"در یک مسئله عددی مربوط به «{c['name']}»، مقدار خواسته‌شده را با دو رقم اعشار محاسبه کن "
                            f"(داده‌های مسئله در صورت سؤال آزمون داده می‌شود).",
                    "answer": {"value": round(base, 2), "tolerance": 0.15, "unit": ""},
                    "explanation": "حل با اعمال تعریف گام‌به‌گام انجام می‌شود؛ خطای محاسبه‌ای رایج، جابه‌جا کردن ترتیب عملیات است.",
                    "difficulty": "MEDIUM",
                    "cognitive_level": "APPLY",
                    "concept_key": c["key"],
                })
            elif t == "ESSAY":
                out.append({
                    "type": "ESSAY",
                    "body": f"مفهوم «{c['name']}» را با یک مثال و یک ضدنمونه توضیح بده و مرز آن با مفاهیم مشابه را روشن کن.",
                    "answer": {"reference": c.get("description") or f"توضیح دقیق {c['name']}"},
                    "explanation": "پاسخ کامل باید تعریف، مثال سازگار، ضدنمونه و تمایز با مفاهیم مشابه را داشته باشد.",
                    "difficulty": "HARD",
                    "cognitive_level": "ANALYZE",
                    "concept_key": c["key"],
                    "misconception": mc[0]["title"] if mc else None,
                    "_rubric": rubric if usage == "QUIZ" else None,
                })
    return {"questions": out}


def mock_syllabus_extraction(inputs: dict) -> dict:
    import re

    text = inputs.get("text", "")
    chapters: list[dict] = []
    objectives: list[str] = []
    ambiguous: list[str] = []
    current = None
    chapter_re = re.compile(r"^(فصل|بخش|chapter)\b[^\d]*", re.I)
    topic_re = re.compile(r"^\d+\.\d+\s*")
    objective_re = re.compile(r"^(هدف|objectives?)", re.I)
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if chapter_re.match(line) and len(line) < 150:
            current = {"title": line, "topics": [], "hours": None}
            chapters.append(current)
        elif topic_re.match(line):
            if current is None:
                current = {"title": "سرفصل اصلی", "topics": [], "hours": None}
                chapters.append(current)
            current["topics"].append(line)
        elif objective_re.match(line) or line.startswith(("-", "*", "•")):
            objectives.append(line.lstrip("-*• ").strip())
        elif current is not None:
            current["topics"].append(line)
        else:
            current = {"title": line, "topics": [], "hours": None}
            chapters.append(current)
    if not chapters:
        ambiguous.append("متن سرفصل ساختار فصل/موضوع مشخصی ندارد؛ ورود دستی لازم است.")
    for ch in chapters:
        if not ch["topics"]:
            ch["topics"] = [ch["title"]]
            ambiguous.append(f"فصل «{ch['title']}» بدون موضوع فرعی؛ پیشنهاد تجزیه نیازمند بررسی است.")
    ambiguous.extend([t for ch in chapters for t in ch["topics"] if len(t) < 5])
    return {"chapters": chapters[:40], "objectives": objectives[:20], "ambiguous": ambiguous[:10]}


def _keyword_overlap(a: str, b: str) -> float:
    wa = set(a.split()) - {"و", "در", "به", "از", "که", "این", "با", "برای", "است", "را"}
    wb = set(b.split()) - {"و", "در", "به", "از", "که", "این", "با", "برای", "است", "را"}
    if not wb:
        return 0.0
    return len(wa & wb) / len(wb)


def mock_essay_grading(inputs: dict) -> dict:
    rubric = inputs.get("rubric") or [{"criterion": "پاسخ", "max_score": 10}]
    reference = inputs.get("reference_answer", "")
    student = inputs.get("student_answer", "")
    ratio = _keyword_overlap(student, reference)
    length_factor = min(1.0, len(student) / 300)
    scores, total, max_total = [], 0.0, 0.0
    for i, crit in enumerate(rubric):
        mx = float(crit.get("max_score", 5))
        max_total += mx
        weight = 0.75 if i == 0 else 0.9
        s = round(mx * min(1.0, (ratio * 1.2 + length_factor * 0.2)) * weight, 1)
        scores.append({
            "criterion": crit.get("criterion", f"معیار {i+1}"),
            "score": min(s, mx),
            "max_score": mx,
            "evidence": (student[:160] + "…") if student else "پاسخ خالی است",
        })
        total += min(s, mx)
    unc = "LOW" if ratio > 0.6 else ("HIGH" if ratio < 0.2 else "MEDIUM")
    return {
        "rubric_scores": scores,
        "total_score": round(total, 1),
        "max_total": max_total,
        "uncertainty": unc,
        "rationale": (
            f"پوشش واژگان کلیدی پاسخ مرجع حدود {ratio:.0%} برآورد شد. این نمره «پیشنهاد AI» است و تا "
            "تأیید استاد رسمی نیست؛ برای پاسخ‌های مرزی، بازبینی انسانی توصیه می‌شود."
        ),
    }


def mock_short_answer_check(inputs: dict) -> dict:
    accepted = " ".join(inputs.get("accepted", []))
    student = inputs.get("student_answer", "")
    ratio = _keyword_overlap(student, accepted)
    return {
        "correct": ratio >= 0.5,
        "confidence": "MEDIUM" if 0.3 < ratio < 0.7 else "LOW",
        "rationale": f"نسبت تطابق معنایی حدود {ratio:.0%}؛ این بررسی معنایی جایگزین پاسخ‌های معتبر تعریف‌شده توسط استاد است و غیرقطعی است.",
    }


def mock_tutor_answer(inputs: dict) -> dict:
    chunks = inputs.get("context_chunks") or []
    mode = inputs.get("mode", "LEARNING")
    help_mode = inputs.get("help_mode") or "EXPLAIN"
    question = inputs.get("question", "")
    weak = inputs.get("learner_state", {}).get("weak_concepts", [])
    lower = question.lower()
    if mode == "ASSESSMENT" and any(w in lower for w in ("پاسخ", "جواب", "کلید", "کدام گزینه")):
        return {
            "answer": "در حالت آزمون، طبق سیاست آزمون فقط توضیح صورت سؤال و اصطلاحات آن مجاز است؛ "
                      "راهنمایی مستقیم به پاسخ ارائه نمی‌شود. اگر صورت سؤال برایت مبهم است، دقیق بگو کدام قسمت را نمی‌فهمی.",
            "citations": [],
            "insufficient_evidence": False,
            "needs_teacher": False,
            "help_mode": "GUIDE",
            "ladder_level": 1,
        }
    ladder_map = {"GUIDE": 1, "PRACTICE": 3, "EXPLAIN": 4}
    ladder_level = ladder_map.get(help_mode, 4)
    if help_mode == "GUIDE":
        ladder_level = 2
        if not chunks:
            return {
                "answer": "برای شروع، یک سؤال راهنما: این مسئله به کدام مفهوم درس شبیه است؟ "
                          "اسم مفهوم را بگو تا از همان‌جا شروع کنیم. فعلاً پاسخ کامل نمی‌دهم تا خودت امتحان کنی.",
                "citations": [],
                "insufficient_evidence": False,
                "needs_teacher": False,
                "help_mode": "GUIDE",
                "ladder_level": 1,
            }
        return {
            "answer": "یک سؤال راهنما (بدون پاسخ کامل): " + chunks[0]["text"][:200]
                      + " … بر اساس این، قدم اول حل چیست؟ اگر گیر کردی، «مثال ساده‌تر» را بخواه.",
            "citations": [{"resource_id": chunks[0]["resource_id"], "locator": chunks[0].get("locator", ""),
                           "quote": chunks[0]["text"][:120]}],
            "insufficient_evidence": False,
            "needs_teacher": False,
            "help_mode": "GUIDE",
            "ladder_level": 2,
        }
    if not chunks:
        return {
            "answer": "در منابع مجاز این درس، مطلب مستقیمی برای این پرسش پیدا نکردم و نمی‌خواهم پاسخ ساختگی بدهم. "
                      "پرسش را با مفهوم‌های درس دقیق‌تر کن یا آن را برای استاد ثبت کن تا پاسخ مؤثر اضافه شود.",
            "citations": [],
            "insufficient_evidence": True,
            "needs_teacher": True,
            "help_mode": help_mode,
            "ladder_level": 0,
        }
    top = chunks[:2]
    parts = [f"بر اساس منابع مجاز درس، خلاصه پاسخ:"]
    for ch in top:
        parts.append("• " + ch["text"][:320])
    if weak:
        parts.append(f"پیشنهاد: پیش از ادامه، مفهوم «{weak[0]}» را مرور کن؛ شواهد یادگیری‌ات نشان می‌دهد آن مفهوم هنوز تثبیت نشده است.")
    if help_mode == "PRACTICE":
        parts.append("حل را با هم جلو می‌بریم: قدم اول را تو بنویس؛ من بررسی و گام بعدی را پیشنهاد می‌دهم.")
    else:
        parts.append("سؤال سقراطی برای تمرین ذهن: اگر همین مفهوم را در یک موقعیت واقعی دیگر به‌کار ببریم، کدام بخش تعریف تغییر نمی‌کند و کدام بخش وابسته به موقعیت است؟")
    return {
        "answer": "\n".join(parts),
        "citations": [{"resource_id": ch["resource_id"], "locator": ch.get("locator", ""),
                       "quote": ch["text"][:120]} for ch in top],
        "insufficient_evidence": False,
        "needs_teacher": False,
        "help_mode": help_mode,
        "ladder_level": ladder_level,
    }


def mock_teach_back_feedback(inputs: dict) -> dict:
    """بازخورد روبرکی «به من یاد بده» — دقت تعریف/پوشش روابط/کیفیت مثال/ابهام‌ها."""
    content = (inputs.get("content") or "").strip()
    concept = inputs.get("concept_name", "مفهوم")
    words = len(content.split()) if content else 0
    has_relation_words = any(w in content for w in ("پیش‌نیاز", "وابسته", "متصل", "بر پایه", "منجر")) if content else False
    has_example = "مثال" in content or "مثلاً" in content or "مثل " in content if content else False
    definition_score = 2.0 if words >= 40 else 1.0 if words >= 15 else 0.5
    coverage_score = 2.0 if has_relation_words else 1.0
    example_score = 2.0 if has_example else 1.0 if words >= 30 else 0.5
    gaps = []
    if not has_relation_words:
        gaps.append(f"ارتباط «{concept}» با مفاهیم پیش‌نیاز یا کاربردهای آن گفته نشده است")
    if not has_example:
        gaps.append("یک مثال واقعی یا حل‌شده اضافه کن تا توضیح ملموس شود")
    follow = (f"خوب بود؛ اگر شرط اصلی «{concept}» برقرار نباشد، نتیجه چه تغییری می‌کند؟ "
              "در یک جمله پاسخ بده تا سطح فهمت را بسنجیم.")
    return {
        "rubric_scores": [
            {"criterion": "دقت تعریف", "score": definition_score, "max_score": 2,
             "evidence": f"طول توضیح: {words} واژه"},
            {"criterion": "پوشش روابط اصلی", "score": coverage_score, "max_score": 2,
             "evidence": "ارتباط با پیش‌نیازها ذکر شد" if has_relation_words else "بدون اشاره به روابط"},
            {"criterion": "کیفیت مثال", "score": example_score, "max_score": 2,
             "evidence": "مثال موجود است" if has_example else "مثالی یافت نشد"},
        ],
        "follow_up_question": follow,
        "gaps": gaps,
        "encouragement": "بازگویی با کلام خودتان یکی از قوی‌ترین ابزارهای تثبیت یادگیری است — ادامه بده!",
    }


def mock_creation_feedback(inputs: dict) -> dict:
    body = (inputs.get("content") or {}).get("body", "")
    concept = inputs.get("concept_name", "مفهوم")
    ok = len(body) > 120
    return {
        "feedback": (
            f"تولید تو درباره «{concept}» بازخوردگیری شد. "
            + ("پوشش مفهومی خوبی دارد و برای بررسی همتا آماده است." if ok else
               "برای ارسال به بررسی همتا، کفایت محتوا را افزایش بده: تعریف دقیق‌تر، یک مثال و یک ضدنمونه اضافه کن.")
        ),
        "strengths": ["استفاده از زبان ساده", "ارتباط با مفهوم درس"] if ok else ["اشاره به مفهوم درست"],
        "improvements": ["اضافه‌کردن یک مثال مرزی", "اشاره به بدفهمی رایج و رد آن"] if ok else
        ["افزودن تعریف دقیق", "افزودن مثال"],
        "approved_for_peer": ok,
    }
