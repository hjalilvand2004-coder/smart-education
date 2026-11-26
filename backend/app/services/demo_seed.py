"""داده نمونه دمو — اجرای کامل خط تولید واقعی سامانه (v3.13.0 — درس‌های واقعی پیوست).

این اسکریپت همه چیز را با سرویس‌های واقعی می‌سازد (نه داده خام):
  کاربران → درس‌ها → ورود سرفصل (از طرح‌های درس مصوب پیوست‌شده) → تأیید →
  مفاهیم → منابع → تولید محتوا → انتشار → بانک سؤال → آزمون → پاسخ دانشجو →
  تسلط → برنامه مطالعه → گفتگو

درس‌های دمو بر اساس چهار «طرح درس مصوب» پیوست کاربر ساخته می‌شوند:
  داده‌کاوی (۳-۲۹) · اینترنت اشیاء (۳-۲۲) · توسعه نرم‌افزار (۳-۶) · آزمون نرم‌افزار (۳-۳۵)
درس اصلی که خط تولید کامل رویش اجرا می‌شود «داده‌کاوی» است؛ سه درس دیگر با
سرفصل مصوب، مفاهیم و منابع واقعی سید می‌شوند تا پنل درس‌ها جذاب و واقعی باشد.

مصرف:
  ۱) خط فرمان:  python scripts/seed_demo.py   (پس از scripts/init_db.py)
  ۲) بوت‌استرپ خودکار نسخهٔ پرتیبل (app/core/bootstrap.py) وقتی دیتابیس خالی است.
اگر دیتابیس نسخهٔ قبلی درس دموی قدیمی (ریاضیات عمومی ۱ — MATH101) را داشته باشد،
همان زنجیرهٔ دادهٔ دمو پاک‌سازی و درس‌های جدید جایگزین می‌شوند (v3.13.0).
"""
import sys

# چاپ فارسی روی کنسول‌های cp1252/cp1256 ویندوز (CI و cmd) بدون کرش —
# ریشهٔ خطای UnicodeEncodeError در گام بذر CI روی رانر ویندوز
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from app.core.database import Base, SessionLocal  # noqa: E402
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

OLD_DEMO_CODE = "MATH101"          # درس دموی نسخه‌های قبل از v3.13.0
DEMO_COURSE_CODES = ("DM-29", "IOT-22", "SWD-06", "ST-35")

# ---------- سرفصل‌های مصوب (برگرفته از طرح‌های درس پیوست کاربر) ----------

SYLLABUS_TEXT_DM = """
درس: داده‌کاوی — کد DM-29 (طرح درس مصوب ۳-۲۹) — مقطع کارشناسی مهندسی کامپیوتر — ۳ واحد (۲ نظری + ۱ عملی)
مرجع تصویب: طرح درس مصوب گروه مهندسی کامپیوتر؛ نوع درس اختیاری، پیش‌نیاز: آمار و احتمالات، جمع ۴۶ ساعت

فصل ۱: مباحث اولیه داده‌کاوی
1.1 تعریف، لزوم و کاربردهای داده‌کاوی در کاربردهای مختلف
1.2 تکنیک‌های یادگیری ماشین؛ یادگیری با ناظر و بدون ناظر
1.3 معرفی ابزارهای متداول داده‌کاوی: Python، R، RapidMiner و WEKA و مقایسه ویژگی‌ها و محدودیت‌ها

فصل ۲: آماده‌سازی داده‌ها
2.1 انواع داده، آن‌ها و خصوصیات و ویژگی‌ها
2.2 جمع‌آوری داده و تغییر شکل داده
2.3 کاهش داده (کاهش صفات و نمونه‌ها) و کار با ابزارهای آماده‌سازی مانند SAS

فصل ۳: الگوهای مکرر و قوانین انجمنی
3.1 تولید الگوهای مکرر
3.2 قوانین انجمنی و الگوریتم Apriori
3.3 الگوریتم FP-Growth و طرح و انجام مثال با ابزارهای متداول

فصل ۴: طبقه‌بندی
4.1 مفهوم طبقه‌بندی، روش‌های متداول و کاربردهای آن
4.2 درخت تصمیم و معیارهای انتخاب صفت (Information Gain، Gain Ratio، Gini Index، CHAID و CART)
4.3 الگوریتم kNN، قانون بیز و انواع فاصله‌سنجی و نرمال‌سازی داده‌ها
4.4 معیارهای ارزیابی طبقه‌بندی: Accuracy، Error Rate، Precision و Recall

فصل ۵: خوشه‌بندی
5.1 مفهوم خوشه‌بندی و کاربردهای آن
5.2 معیارهای تشابه و انواع داده (دودویی، پیوسته و کیفی)
5.3 الگوریتم‌های خوشه‌بندی مانند K-Means و طرح و انجام مثال با ابزارهای متداول

فصل ۶: کاربردهای داده‌کاوی
6.1 سیستم‌های پیشنهاددهنده و فیلتر مشارکتی؛ معیارهای شباهت و پیش‌بینی رتبه
6.2 تحلیل نمودارهای بزرگ و فرمول گوگل برای رتبه صفحه

فصل ۷: انبار داده
7.1 اجزاء و شمای انبار داده
7.2 تحلیل داده و OLAP؛ کار با Microsoft SQL Server Data Tools

اهداف یادگیری:
- تمایز یادگیری با ناظر و بدون ناظر و انتخاب تکنیک مناسب برای مسئله
- تولید الگوهای مکرر و قوانین انجمنی با الگوریتم‌های Apriori و FP-Growth
- ساخت و ارزیابی مدل طبقه‌بندی با درخت تصمیم و kNN و معیارهای Precision و Recall
- خوشه‌بندی داده‌ها با K-Means و تفسیر نتایج
"""

SYLLABUS_TEXT_IOT = """
درس: اینترنت اشیاء — کد IOT-22 (طرح درس مصوب ۳-۲۲) — مقطع کارشناسی مهندسی کامپیوتر — ۳ واحد (۲ نظری + ۱ عملی)
مرجع تصویب: طرح درس مصوب گروه مهندسی کامپیوتر؛ نوع درس تخصصی، جمع ۴۶ ساعت

فصل ۱: شناخت مفاهیم نظری اینترنت اشیاء
1.1 مفاهیم پایه، تعریف، اهمیت و دامنه‌های کاربرد؛ سیر تکامل و اکوسیستم
1.2 استانداردهای مطرح، مزایا و چالش‌های اینترنت اشیاء و مدل‌ها و معماری‌های مرجع

فصل ۲: زیرساخت اینترنت اشیاء
2.1 دستگاه‌ها، اشیاء، حسگرها و عملگرها؛ شبکه‌های حسگر بیسیم
2.2 انواع استانداردهای شبکه کامپیوتری و تعامل‌ها، سازگاری و پروتکل‌های موردنیاز در لایه ارتباطات

فصل ۳: سرویس‌ها و لایه کاربرد
3.1 سرویس‌ها و معماری سرویس‌گرا در لایه کاربرد؛ پلتفرم‌های اینترنت اشیاء
3.2 چالش‌های تطبیق، امنیت و حریم خصوصی اینترنت اشیاء

فصل ۴: کار عملی با سخت‌افزار
4.1 آشنایی و نحوه کار با انواع حسگرها، عملگرها و میکروکنترلرها
4.2 کار عملی با پلتفرم‌های سخت‌افزاری متداول مانند Raspberry Pi و Arduino و ماژول‌های Wi-Fi، Bluetooth و Ethernet

فصل ۵: سیستم‌عامل و شبیه‌سازی
5.1 سیستم‌عامل اینترنت اشیاء مانند Contiki و شبیه‌ساز مانند Cooja
5.2 انجام یک پروژه عملی در حوزه اینترنت اشیا

اهداف یادگیری:
- توصیف اکوسیستم و معماری‌های مرجع اینترنت اشیاء
- انتخاب پروتکل و ماژول ارتباطی مناسب برای یک سناریوی واقعی
- برنامه‌نویسی عملی روی پلتفرم‌های Raspberry Pi و Arduino
"""

SYLLABUS_TEXT_SW = """
درس: توسعه نرم‌افزار — کد SWD-06 (طرح درس مصوب ۳-۶) — مقطع کارشناسی مهندسی کامپیوتر — ۳ واحد (۲ نظری + ۱ عملی)
مرجع تصویب: طرح درس مصوب گروه مهندسی کامپیوتر؛ نوع درس تخصصی، پیش‌نیاز: مهندسی نرم‌افزار، جمع ۴۶ ساعت

فصل ۱: گیت و جریان توسعه
1.1 مقدمات و آشنایی با گیت؛ اولین init، کامیت و بررسی تغییرات و تاریخچه
1.2 شاخه‌ها (branch) و آشنایی و استفاده از گیت‌هاب
1.3 بررسی و حل کانفلیکت‌ها، merge، تگ زدن برای شناسایی نسخه‌ها و دیباگ با کمک گیت
1.4 مشارکت در پروژه‌های گیت‌لب و گیت‌هاب؛ code review تیمی بین دانشجویان

فصل ۲: اسکرام و کانبان
2.1 آشنایی با مفاهیم کلی و تفاوت‌های اسکرام و کانبان؛ نقش‌ها و مراسم
2.2 مصنوعات و قراردادهای اسکرام و کانبان؛ چرخه حیات یک استوری
2.3 نحوه کار تحت چارچوب اسکرام و کانبان؛ اجرای اسپرینت نمونه شامل استوری‌ها

فصل ۳: محیط توسعه
3.1 نصب محیط یکپارچه توسعه (IDE) مانند VSCode، PyCharm یا WebStorm به انتخاب مدرس
3.2 نصب پکیج‌های عمومی و اختصاصی و استفاده از رجیستری‌ها؛ اتصال گیت و IDE
3.3 آشنایی با محیط‌های Development، Staging و Production و ایجاد محیط پایدار برای Buildها

فصل ۴: ترلو و جیرا
4.1 آشنایی کار با ترلو؛ ایجاد کارت و بورد
4.2 آشنایی با ابزار جیرا؛ ایجاد و ویرایش issue، جستجو و فیلتر، roadmap، داشبورد و بورد
4.3 آشنایی به issue tracking در گیت‌لب و ایجاد پروژه تیمی توسط دانشجویان

فصل ۵: تست و مستندسازی نرم‌افزار
5.1 آشنایی با تست دستی و اتوماتیک نرم‌افزار و ابزارهای آن؛ Unit Test و Integration Test
5.2 آشنایی با مفهوم مستندسازی در مدل‌های چابک؛ مستندسازی نیازمندی و طراحی و معماری
5.3 مستندسازی کد و API و ابزارهای مرتبط (Read the Docs)؛ استفاده از ابزارهای مستندسازی در گیت‌هاب و گیت‌لب

اهداف یادگیری:
- مدیریت نسخه و کار تیمی با گیت و گیت‌هاب شامل حل کانفلیکت
- اجرای اسپرینت اسکرام با استوری‌ها و مراسم واقعی
- پیاده‌سازی پروژه تیمی در محیط توسعه با مدیریت کار در جیرا
"""

SYLLABUS_TEXT_ST = """
درس: آزمون نرم‌افزار — کد ST-35 (طرح درس مصوب ۳-۳۵) — مقطع کارشناسی مهندسی کامپیوتر — ۳ واحد (۲ نظری + ۱ عملی)
مرجع تصویب: طرح درس مصوب گروه مهندسی کامپیوتر؛ نوع درس اختیاری، پیش‌نیاز: مهندسی نرم‌افزار، جمع ۴۶ ساعت

فصل ۱: چرایی آزمون نرم‌افزار
1.1 فعالیت‌ها و مشاغل آزمون نرم‌افزار و آشنایی با بازار کار و نیازمندی‌ها

فصل ۲: معیارهای مبتنی بر ورودی
2.1 معیارهای آزمون و معیارهای پوشش؛ ورودی از طریق واسط کاربری و ورودی تابع
2.2 افراز فضای ورودی و مقادیر؛ بررسی مدل ایجاد شده، انتخاب بلوک و استراتژی‌های ترکیبی
2.3 محدودیت‌های بین افرازها و مطالعه موردی

فصل ۳: معیارهای مبتنی بر گراف
3.1 فرآیند و معیارهای آزمون؛ پوشش مبتنی بر ساختار و جریان داده و پوشش مبتنی بر مسیر کد
3.2 پوشش مبتنی بر Use Case و مطالعه موردی

فصل ۴: معیارهای مبتنی بر منطق
4.1 فرآیند و معیارهای آزمون؛ ماشین حالت متناهی و معیارهای پوشش منطقی آن
4.2 مطالعه موردی

فصل ۵: خودکارسازی آزمون
5.1 ابزارهای آزمون خودکار مانند JUnit؛ طراحی و پیاده‌سازی آزمون‌ها
5.2 ملاحظات عملی آزمون نرم‌افزار
5.3 سرفصل‌های تکمیلی به نسبت زمان: معیارهای مبتنی بر نحو، آزمون اجزای UI، آزمون Web end-to-end و آزمون امنیت

اهداف یادگیری:
- طراحی آزمون بر اساس معیارهای افراز فضای ورودی
- طراحی آزمون با معیارهای گراف و پوشش مسیر کد
- خودکارسازی آزمون با JUnit برای یک پروژه واقعی
"""

RESOURCE_TEXTS_DM = {
    "کتاب درسی — الگوهای مکرر و قوانین انجمنی": (
        "الگوهای مکرر: مجموعه‌ای از آیتم‌ها که در تراکنش‌ها با پشتیبانی (support) بیش از حد آستانه "
        "تکرار می‌شوند؛ پایه تحلیل سبد خرید و کشف قوانین انجمنی است.\n\n"
        "قانون انجمنی X→Y با دو سنجه سنجیده می‌شود: پشتیبانی (نسبت تراکنش‌های شامل X و Y) و "
        "اطمینان (confidence؛ نسبت تراکنش‌های شامل Y میان تراکنش‌های شامل X).\n\n"
        "الگوریتم Apriori: بر ویژگی مرتبت‌بودن زیرمجموعه تکیه دارد — هر زیرمجموعهٔ یک مجموعه مکرر "
        "هم مکرر است؛ بنابراین پس از هر مرحله، ابرمجموعه‌هایی که زیرمجموعه کم‌تکرار دارند حذف می‌شوند "
        "و شمارش کاندیدها به‌شدت کم می‌شود.\n\n"
        "الگوریتم FP-Growth: به‌جای تولید کاندیدها، درخت FP-Tree فشرده می‌سازد و الگوهای مکرر را "
        "با دو بار پیمایش داده استخراج می‌کند؛ برای داده‌های متراکم معمولاً از Apriori سریع‌تر است."
    ),
    "جزوه استاد — طبقه‌بندی با درخت تصمیم": (
        "درخت تصمیم: مدل طبقه‌بندی که داده‌ها را بر اساس پرسش‌های متوالی روی صفات به برگ‌های "
        "برچسب‌دار می‌رساند. انتخاب صفت ریشهٔ هر گره با سنجه ناخالصی انجام می‌شود.\n\n"
        "Information Gain: کاهش انتروپی پس از افراز با یک صفت؛ Gain Ratio همان کاهش را با تقسیم بر "
        "اطلاعات افراز تصحیح می‌کند تا صفات با مقادیر زیاد ترجیح بی‌دلیل نباشند. Gini ناخالصی احتمال "
        "طبقه‌بندی اشتباه یک نمونه تصادفی است و پایه الگوریتم CART است.\n\n"
        "kNN: نمونه جدید با رأی اکثریت میان k همسایه نزدیک برچسب می‌خورد؛ انتخاب k و نرمال‌سازی "
        "صفات (چون فاصله‌سنجی مبنای مقایسه است) اهمیت دارد.\n\n"
        "ارزیابی: Accuracy نسبت کل درست‌هاست؛ اما در داده‌های نامتوازن گمراه‌کننده است. Precision "
        "دقت پیش‌بینی‌های مثبت و Recall پوشش مثبت‌های واقعی را می‌سنجد؛ F1 میانگین توازن آن‌هاست.\n\n"
        "بدفهمی رایج: «درخت بزرگ‌تر یعنی مدل بهتر» — اشتباه است؛ رشد بی‌رویه درخت بیش‌برازش می‌آورد "
        "و هرس (pruning) لازم است. بدفهمی دوم: «Accuracy بالا یعنی مدل خوب» — روی داده نامتوازن نه."
    ),
    "کلید امتحان میان‌ترم (محرمانه)": (
        "کلید امتحان میان‌ترم — پاسخ سؤال ۱: پشتیبانی مجموعه {A,B} برابر 0.25 و اطمینان قانون A→B "
        "برابر 0.5 است. پاسخ سؤال ۲: صفت با Information Gain بیشتر برای ریشه انتخاب می‌شود. "
        "این سند محرمانه است و فقط برای تصحیح رسمی استفاده می‌شود."
    ),
}

RESOURCE_TEXTS_SIDE = {
    "IOT-22": (
        "کتاب درسی — Getting Started with the Internet of Things (Cuno Pfister): لایه‌های معماری اینترنت "
        "اشیاء از حسگر و میکروکنترلر تا اتصال ابری؛ پروتکل‌های سبک برای دستگاه‌های کم‌توان و "
        "الگوی «به‌روزشدانی وضعیت» برای ارسال داده حسگر به سرویس ابری.\n\n"
        "نکات عملی: انتخاب ماژول ارتباطی (Wi-Fi، Bluetooth، Ethernet) بر اساس مصرف توان و برد؛ "
        "شبیه‌سازی شبکه با Cooja برای سیستم‌عامل Contiki پیش از استقرار واقعی."
    ),
    "SWD-06": (
        "کتاب درسی — Scrum: The Art of Doing Twice the Work in Half the Time (Jeff Sutherland و J.J. Sutherland): "
        "چارچوب اسکرام با اسپرینت‌های ثابت کوتاه؛ دامنه متغیر و زمان ثابت.\n\n"
        "نکات عملی: مراسم روزانه کوتاه، بازبینی و بازنگری اسپرینت؛ مدیریت کار با بورد کانبان و "
        "جیرا (issue، فیلتر، roadmap)؛ کنترل نسخه تیمی با گیت و گیت‌هاب و حل کانفلیکت پیش از merge."
    ),
    "ST-35": (
        "کتاب درسی — Introduction to Software Testing (Paul Ammann و Jeff Offutt): آزمون منظم بر پایه "
        "معیارها؛ معیارهای مبتنی بر ورودی (افراز فضای ورودی و ترکیب بلوک‌ها)، مبتنی بر گراف "
        "(پوشش گره و یال و مسیر) و مبتنی بر منطق (پوشش شروط).\n\n"
        "نکات عملی: خودکارسازی با JUnit؛ انتخاب معیار مناسب بر اساس هزینه و کشف خطا؛ "
        "در داده نامتوازن دقت تنها کافی نیست و Precision و Recall باید گزارش شوند."
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


def purge_demo_courses(db, codes: tuple[str, ...]) -> None:
    """حذف کامل زنجیرهٔ دادهٔ درس‌های دمو (گرفته از طرح‌های درس با کد مشخص).

    از گراف FK متادیتا، فرزندانِ فرزندان (مثلاً پاسخ‌ها ← تلاش‌ها ← آزمون‌ها ← درس)
    را با شناسه‌های واقعی پیدا و از برگ به ریشه حذف می‌کند — فقط دموی قدیمی و
    نه کاربران/تنظیمات/حسابرسی (v3.13.0 برای ارتقای دیتابیس‌های نسخهٔ قبل).
    """
    courses = db.query(Course).filter(Course.code.in_(codes)).all()
    if not courses:
        return
    # نگاشت هر FK: (جدول فرزند، ستون) ← (جدول والد، ستون)
    fk_map: dict[tuple[str, str], tuple[str, str]] = {}
    for t in Base.metadata.tables.values():
        for fk in t.foreign_keys:
            fk_map[(t.name, fk.parent.name)] = (fk.column.table.name, fk.column.name)

    doomed: list[tuple[str, str, list]] = []  # (جدول، ستون FK، شناسه‌ها) از ریشه به برگ
    frontier = [("courses", "id", [str(c.id) for c in courses])]
    seen = {"courses"}
    from sqlalchemy import select as _select

    while frontier:
        nxt = []
        for ptable, _pcol, pids in frontier:
            # انتشار با PK والد («id») تا نوه‌ها هم پیدا شوند؛ حذف با ستون FK فرزند
            for (ctable, ccol), (ptable2, _pcol2) in fk_map.items():
                if ptable2 == ptable and _pcol2 == "id" and ctable not in seen:
                    seen.add(ctable)
                    tbl = Base.metadata.tables[ctable]
                    rows = db.execute(
                        _select(getattr(tbl.c, ccol))
                        .where(getattr(tbl.c, ccol).in_(pids))).fetchall()
                    ids = [r[0] for r in rows]
                    if ids:
                        doomed.append((ctable, ccol, ids))
                        nxt.append((ctable, "id", ids))
        frontier = nxt
    for ctable, ccol, ids in reversed(doomed):
        tbl = Base.metadata.tables[ctable]
        db.execute(tbl.delete().where(getattr(tbl.c, ccol).in_(ids)))
    db.execute(Base.metadata.tables["courses"]
               .delete().where(Course.id.in_([c.id for c in courses])))
    db.flush()
    print(f"purged old demo courses {codes} (chains removed)")


def _import_and_approve(db, prof, course: Course, text: str) -> SyllabusVersion:
    """ورود سرفصل مصوب از متن طرح درس و تأیید نسخه."""
    job = run_job_sync(db, "syllabus_import",
                       {"course_id": str(course.id), "text": text, "source_kind": "TEXT"}, prof)
    sv = db.get(SyllabusVersion, job.result["syllabus_version_id"])
    print(f"  syllabus imported: v{sv.version_number} ambiguous={bool(sv.ambiguous_notes)}")
    sv = approve_version(db, sv, prof, "تأیید هیئت مؤلفان")
    print(f"  syllabus approved: v{sv.version_number}")
    return sv


def _add_resource(db, course: Course, prof, title: str, text: str, exam_key: bool = False) -> Resource:
    res = Resource(
        course_id=course.id, title=title,
        kind="EXAM_KEY" if exam_key else "TEXTBOOK",
        language="FA", license="مالکیت گروه", uploaded_by=prof.id,
        contains_exam_material=exam_key,
    )
    db.add(res)
    db.flush()
    rag.index_resource_text(db, res, text)
    db.add(ResourcePermission(resource_id=res.id, course_id=course.id))
    db.flush()
    return res


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        new_exists = db.query(Course).filter(Course.code.in_(DEMO_COURSE_CODES)).first()
        old_exists = db.query(Course).filter(Course.code == OLD_DEMO_CODE).first()
        if old_exists:
            purge_demo_courses(db, (OLD_DEMO_CODE,))
            db.commit()
        if new_exists:
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
        # مقاطع متنوع برای نمایش پرزنت متناسب با مقطع (v3.12.0)
        st1.degree_level = "KARSHENASI"
        st2.degree_level = "ARASTD"
        edu = mk_user("edu.admin", "مدیر آموزشی گروه", Role.EDUCATION_ADMIN.value)
        quality = mk_user("quality.expert", "کارشناس کیفیت محتوا", Role.QUALITY_REVIEWER.value)
        tech = mk_user("tech.admin", "مدیر فنی", Role.TECH_ADMIN.value)
        db.flush()

        # ---------- چهار درس واقعی از طرح‌های درس مصوب پیوست (v3.13.0) ----------
        def mk_course(code, title, description, term="نیم‌سال جاری"):
            c = Course(code=code, title=title, department="گروه مهندسی کامپیوتر",
                       degree_level="کارشناسی", field_of_study="مهندسی کامپیوتر", credits=3,
                       term=term, description=description, created_by=prof.id)
            db.add(c)
            db.flush()
            off = CourseOffering(course_id=c.id, term=term, professor_id=prof.id)
            db.add(off)
            db.flush()
            for role in (Role.PROFESSOR, Role.ASSISTANT, Role.GROUP_ADMIN):
                db.add(CourseRole(course_id=c.id, user_id=(ta if role is Role.ASSISTANT else edu if role is Role.GROUP_ADMIN else prof).id,
                                  role=role.value, granted_by=prof.id))
            for st in (st1, st2):
                db.add(Enrollment(offering_id=off.id, student_id=st.id))
            db.flush()
            return c, off

        course, offering = mk_course(
            "DM-29", "داده‌کاوی",
            "درس اختیاری — پیش‌نیاز: آمار و احتمالات — ۲ نظری + ۱ عملی (۴۶ ساعت) — "
            "بر اساس طرح درس مصوب گروه (کد ۳-۲۹)")
        iot_course, _ = mk_course(
            "IOT-22", "اینترنت اشیاء",
            "درس تخصصی — ۲ نظری + ۱ عملی (۴۶ ساعت) — بر اساس طرح درس مصوب گروه (کد ۳-۲۲) — "
            "شامل پروژه عملی با Raspberry Pi و Arduino")
        sw_course, _ = mk_course(
            "SWD-06", "توسعه نرم‌افزار",
            "درس تخصصی — پیش‌نیاز: مهندسی نرم‌افزار — ۲ نظری + ۱ عملی (۴۶ ساعت) — "
            "بر اساس طرح درس مصوب گروه (کد ۳-۶) — پروژه‌محور با گیت، اسکرام و جیرا")
        st_course, _ = mk_course(
            "ST-35", "آزمون نرم‌افزار",
            "درس اختیاری — پیش‌نیاز: مهندسی نرم‌افزار — ۲ نظری + ۱ عملی (۴۶ ساعت) — "
            "بر اساس طرح درس مصوب گروه (کد ۳-۳۵)")

        # ---------- ورود سرفصل مصوب داده‌کاوی (خط واقعی) ----------
        sv = _import_and_approve(db, prof, course, SYLLABUS_TEXT_DM)

        # ---------- مفاهیم گراف داده‌کاوی ----------
        topics = {t.title: t for t in db.query(SyllabusTopic)
                  .filter(SyllabusTopic.syllabus_version_id == sv.id).all()}

        def topic(title_part):
            return next(t for k, t in topics.items() if title_part in k)

        c_dm = concept_service.create_concept(
            db, course.id, prof, "data_mining", "داده‌کاوی",
            "کشف الگوهای معتبر و ناشناخته در حجم زیاد داده با تکنیک‌های یادگیری ماشین و آمار.",
            topic_ids=[topic("تعریف، لزوم و کاربردهای داده‌کاوی").id], status="APPROVED",
            misconceptions=[{"title": "داده‌کاوی همان آمار توصیفی است",
                             "correction_hint": "آمار توصیفی خلاصه‌سازی است؛ داده‌کاوی کشف الگوی پنهان و پیش‌بینی است."}])
        c_supervised = concept_service.create_concept(
            db, course.id, prof, "supervised_learning", "یادگیری با ناظر",
            "یادگیری از داده‌های برچسب‌دار برای پیش‌بینی خروجی (طبقه‌بندی و رگرسیون).",
            topic_ids=[topic("یادگیری با ناظر و بدون ناظر").id],
            prerequisite_ids=[c_dm.id], status="APPROVED")
        c_unsupervised = concept_service.create_concept(
            db, course.id, prof, "unsupervised_learning", "یادگیری بدون ناظر",
            "کشف ساختار در داده‌های بدون برچسب؛ مانند خوشه‌بندی و کشف قوانین انجمنی.",
            topic_ids=[topic("یادگیری با ناظر و بدون ناظر").id],
            prerequisite_ids=[c_dm.id], status="APPROVED")
        c_prep = concept_service.create_concept(
            db, course.id, prof, "data_preparation", "آماده‌سازی داده‌ها",
            "جمع‌آوری، تغییر شکل و کاهش داده (کاهش صفات و نمونه‌ها) پیش از مدل‌سازی.",
            topic_ids=[topic("جمع‌آوری داده و تغییر شکل داده").id],
            prerequisite_ids=[c_dm.id], status="APPROVED")
        c_freq = concept_service.create_concept(
            db, course.id, prof, "frequent_patterns", "الگوهای مکرر",
            "مجموعه آیتم‌هایی که با پشتیبانی بیش از آستانه در تراکنش‌ها تکرار می‌شوند.",
            topic_ids=[topic("تولید الگوهای مکرر").id],
            prerequisite_ids=[c_unsupervised.id, c_prep.id], status="APPROVED")
        c_apriori = concept_service.create_concept(
            db, course.id, prof, "apriori", "الگوریتم Apriori",
            "تولید الگوهای مکرر و قوانین انجمنی با ویژگی مرتبت‌بودن زیرمجموعه و حذف مرحله‌ای کاندیدها.",
            topic_ids=[topic("قوانین انجمنی و الگوریتم Apriori").id],
            prerequisite_ids=[c_freq.id], status="APPROVED",
            misconceptions=[{"title": "Apriori برای هر داده‌ای سریع‌ترین است",
                             "correction_hint": "روی داده‌های متراکم FP-Growth معمولاً سریع‌تر است چون کاندید تولید نمی‌کند."}])
        c_fpg = concept_service.create_concept(
            db, course.id, prof, "fp_growth", "الگوریتم FP-Growth",
            "استخراج الگوهای مکرر با ساخت درخت FP-Tree فشرده بدون تولید کاندید.",
            topic_ids=[topic("الگوریتم FP-Growth").id],
            prerequisite_ids=[c_freq.id], status="APPROVED")
        c_class = concept_service.create_concept(
            db, course.id, prof, "classification", "طبقه‌بندی",
            "یادگیری با ناظر برای نسبت‌دادن نمونه‌ها به کلاس‌های از پیش تعریف‌شده.",
            topic_ids=[topic("مفهوم طبقه‌بندی، روش‌های متداول").id],
            prerequisite_ids=[c_supervised.id, c_prep.id], status="APPROVED")
        c_tree = concept_service.create_concept(
            db, course.id, prof, "decision_tree", "درخت تصمیم",
            "مدل طبقه‌بندی با پرسش‌های متوالی روی صفات؛ انتخاب صفت هر گره با Information Gain یا Gini.",
            topic_ids=[topic("درخت تصمیم و معیارهای انتخاب صفت").id],
            prerequisite_ids=[c_class.id], status="APPROVED",
            misconceptions=[{"title": "درخت بزرگ‌تر همیشه مدل بهتری است",
                             "correction_hint": "رشد بی‌رویه بیش‌برازش می‌آورد؛ درخت باید هرس شود."}])
        c_gini = concept_service.create_concept(
            db, course.id, prof, "gini_index", "شاخص جینی",
            "ناخالصی احتمال طبقه‌بندی اشتباه یک نمونه تصادفی؛ پایه الگوریتم CART.",
            topic_ids=[topic("درخت تصمیم و معیارهای انتخاب صفت").id],
            prerequisite_ids=[c_tree.id], status="APPROVED")
        c_knn = concept_service.create_concept(
            db, course.id, prof, "knn", "الگوریتم kNN",
            "طبقه‌بندی با رأی اکثریت میان k نزدیک‌ترین همسایه بر اساس فاصله‌سنجی.",
            topic_ids=[topic("الگوریتم kNN، قانون بیز").id],
            prerequisite_ids=[c_class.id], status="APPROVED")
        c_eval = concept_service.create_concept(
            db, course.id, prof, "evaluation", "ارزیابی طبقه‌بندی",
            "Accuracy، Error Rate، Precision و Recall؛ در داده نامتوازن Precision/Recall گویاترند.",
            topic_ids=[topic("معیارهای ارزیابی طبقه‌بندی").id],
            prerequisite_ids=[c_tree.id], status="APPROVED",
            misconceptions=[{"title": "Accuracy بالا همیشه یعنی مدل خوب",
                             "correction_hint": "روی داده نامتوازن مدل تنبل هم Accuracy بالا دارد؛ Precision و Recall را ببینید."}])
        c_cluster = concept_service.create_concept(
            db, course.id, prof, "clustering", "خوشه‌بندی",
            "گروه‌بندی داده‌های بدون برچسب بر اساس معیارهای تشابه.",
            topic_ids=[topic("مفهوم خوشه‌بندی و کاربردهای آن").id],
            prerequisite_ids=[c_unsupervised.id], status="APPROVED")
        c_kmeans = concept_service.create_concept(
            db, course.id, prof, "kmeans", "الگوریتم K-Means",
            "خوشه‌بندی با k مرکز؛ تخصیص نقاط به نزدیک‌ترین مرکز و به‌روزرسانی تکراری مراکز.",
            topic_ids=[topic("الگوریتم‌های خوشه‌بندی مانند K-Means").id],
            prerequisite_ids=[c_cluster.id], status="APPROVED")
        c_recomm = concept_service.create_concept(
            db, course.id, prof, "recommender", "سیستم پیشنهاددهنده",
            "پیشنهاد بر اساس شباهت کاربران/آیتم‌ها (فیلتر مشارکتی) و معیارهای شباهت.",
            topic_ids=[topic("سیستم‌های پیشنهاددهنده").id],
            prerequisite_ids=[c_knn.id], status="APPROVED")
        c_warehouse = concept_service.create_concept(
            db, course.id, prof, "data_warehouse", "انبار داده",
            "مخزن موضوع‌محور و تاریخی داده یکپارچه؛ پایه تحلیل OLAP.",
            topic_ids=[topic("اجزاء و شمای انبار داده").id],
            prerequisite_ids=[c_dm.id], status="APPROVED")
        concept_service.add_relation(db, prof, c_knn, c_recomm, "APPLIED_IN")
        print("concepts: 16 created (داده‌کاوی تا انبار داده)")

        # ---------- منابع واقعی طرح درس + قطعه‌بندی RAG ----------
        r1 = _add_resource(db, course, prof,
                           "کتاب درسی — الگوهای مکرر و قوانین انجمنی",
                           RESOURCE_TEXTS_DM["کتاب درسی — الگوهای مکرر و قوانین انجمنی"])
        r2 = _add_resource(db, course, prof,
                           "جزوه استاد — طبقه‌بندی با درخت تصمیم",
                           RESOURCE_TEXTS_DM["جزوه استاد — طبقه‌بندی با درخت تصمیم"])
        r3 = _add_resource(db, course, prof, "کلید امتحان میان‌ترم (محرمانه)",
                           RESOURCE_TEXTS_DM["کلید امتحان میان‌ترم (محرمانه)"], exam_key=True)
        resources = [r1, r2, r3]
        print("resources: 3 (کلید امتحان علامت‌گذاری شد و از RAG حذف می‌شود)")

        # ---------- استودیو: تولید محتوا (خط واقعی) ----------
        doc = create_document(db, prof, {
            "course_id": str(course.id), "syllabus_version_id": str(sv.id),
            "title": "آموزش مفهوم درخت تصمیم",
            "goal": "CONCEPT_TEACHING", "scope": {"concept_ids": [str(c_tree.id), str(c_eval.id)]},
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
            "concept_ids": [str(c.id) for c in (c_tree, c_apriori, c_kmeans, c_eval, c_knn)],
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
            "title": "کوییز الگوهای مکرر و Apriori", "kind": "QUIZ", "mode": "FIXED",
            "blueprint": {"sections": [
                {"concept_ids": [str(c_freq.id), str(c_apriori.id)], "count": 3, "difficulty": "MEDIUM"},
                {"concept_ids": [str(c_fpg.id)], "count": 1, "difficulty": None},
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
                ans = {"text": ("الگوریتم Apriori با ویژگی مرتبت‌بودن زیرمجموعه، کاندیدهای کم‌تکرار را حذف می‌کند "
                                "و از تراکنش‌ها قوانین انجمنی می‌سازد."
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
            "title": "تمرین تطبیقی طبقه‌بندی و خوشه‌بندی", "kind": "PRACTICE", "mode": "ADAPTIVE_PRACTICE",
            "blueprint": {"sections": [{"concept_ids": [str(c.id) for c in (c_class, c_tree, c_gini, c_eval, c_knn, c_cluster, c_kmeans)], "count": 12}]},
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
                ans = {"text": qv.answer.get("accepted", [""])[0] if qv.answer.get("accepted") else "پشتیبانی مجموعه آیتم‌ها"}
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
            "title": "تمرین طبقه‌بندی", "kind": "PRACTICE", "mode": "FIXED",
            "blueprint": {"sections": [
                {"concept_ids": [str(c_class.id), str(c_tree.id)], "count": 4, "difficulty": None},
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
            "title": "تمرین تشریحی درخت تصمیم", "kind": "PRACTICE", "mode": "FIXED",
            "blueprint": {"sections": [{"concept_ids": [str(c_tree.id)], "count": 3, "difficulty": "HARD"}]},
            "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": False},
        })
        attempt4 = assessment_service.start_attempt(db, essay_assessment, st1)
        for qv_id in (attempt4.question_version_ids or []):
            qv = db.get(QuestionVersion, qv_id)
            q = db.get(Question, qv.question_id)
            if q.type in ("ESSAY", "CASE"):
                ans = {"text": "درخت تصمیم مدل طبقه‌بندی است که با پرسش‌های متوالی روی صفات داده‌ها را به برگ‌های "
                               "برچسب‌دار می‌رساند. انتخاب صفت هر گره با Information Gain یا Gini انجام می‌شود؛ "
                               "مثلاً در سبد خرید، صفت با بیشترین کاهش انتروپی ریشه می‌شود. درخت بزرگ بیش‌برازش "
                               "می‌کند و باید هرس شود؛ ارزیابی با Precision و Recall انجام می‌گیرد. "}
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
        msg = tutor_service.answer(db, session, "درخت تصمیم دقیقاً چیست و چه تفاوتی با خوشه‌بندی دارد؟")
        db.commit()
        print(f"tutor answered: {msg.content[:60]}… citations={len(msg.citations or [])}")

        # ---------- مشارکت دانشجو ----------
        creation = collaboration_service.create_creation(db, st1, str(course.id), {
            "activity_type": "EXPLANATION",
            "concept_id": str(c_apriori.id),
            "content": {"title": "توضیح من: الگوریتم Apriori", "body":
                        "Apriori می‌گوید هر زیرمجموعهٔ یک مجموعه مکرر هم مکرر است؛ پس با حذف مرحله‌ای "
                        "کاندیدهای کم‌تکرار، قوانین انجمنی سبدهای خرید را پیدا می‌کنیم. "
                        "مثال: اگر {نان، کره} مکرر نیست، هیچ ابرمجموعه‌ای از آن بررسی نمی‌شود."},
        })
        collaboration_service.submit_creation(db, creation, st1)
        db.commit()
        print(f"student creation: {creation.status}")

        # ---------- سه درس دیگر: سرفصل مصوب + مفاهیم + منابع واقعی ----------
        for c_code, text, cdefs, res_title in (
            ("IOT-22", SYLLABUS_TEXT_IOT,
             [("iot_basics", "اینترنت اشیاء",
               "اکوسیستم دستگاه‌های متصل با حسگر و عملگر و معماری‌های مرجع لایه‌ای.", "مفاهیم پایه، تعریف، اهمیت"),
              ("sensor_actuator", "حسگر و عملگر",
               "حسگر داده فیزیکی را می‌خواند و عملگر بر محیط اثر می‌گذارد؛ میکروکنترلر واسط دو طرف است.", "حسگرها و عملگرها")],
             "کتاب درسی — Getting Started with the Internet of Things"),
            ("SWD-06", SYLLABUS_TEXT_SW,
             [("git_flow", "کنترل نسخه با گیت",
               "مدیریت تاریخچه و شاخه‌ها و حل کانفلیکت؛ پایه کار تیمی روی گیت‌هاب و گیت‌لب.", "مقدمات و آشنایی با گیت"),
              ("scrum_kanban", "اسکرام و کانبان",
               "چارچوب چابک با اسپرینت‌های ثابت و بورد جریان کار؛ تفاوت نقش‌ها و مراسم.", "اسکرام و کانبان")],
             "کتاب درسی — Scrum: هنر انجام دو برابر کار در نصف زمان"),
            ("ST-35", SYLLABUS_TEXT_ST,
             [("input_partition", "افراز فضای ورودی",
               "تقسیم فضای ورودی به بلوک‌های هم‌ارز و انتخاب مقدارها برای طراحی آزمون.", "افراز فضای ورودی"),
              ("test_automation", "خودکارسازی آزمون با JUnit",
               "نوشتن آزمون‌های واحد قابل تکرار و اجرای خودکار در هر Build.", "ابزارهای آزمون خودکار")],
             "کتاب درسی — Introduction to Software Testing"),
        ):
            c = db.query(Course).filter(Course.code == c_code).first()
            print(f"course {c_code}:")
            svx = _import_and_approve(db, prof, c, text)
            topicx = {t.title: t for t in db.query(SyllabusTopic)
                      .filter(SyllabusTopic.syllabus_version_id == svx.id).all()}
            prev = None
            for key, title, definition, tpart in cdefs:
                cc = concept_service.create_concept(
                    db, c.id, prof, key, title, definition,
                    topic_ids=[next(t for k, t in topicx.items() if tpart in k).id],
                    prerequisite_ids=([prev.id] if prev else []), status="APPROVED")
                prev = cc
            _add_resource(db, c, prof, res_title, RESOURCE_TEXTS_SIDE[c_code])
            print(f"  concepts: {len(cdefs)} | resources: 1")

        db.commit()
        print("\n=== DEMO READY ===")
        print("درس‌های دمو (بر اساس طرح‌های درس مصوب پیوست): داده‌کاوی DM-29 | اینترنت اشیاء IOT-22 | "
              "توسعه نرم‌افزار SWD-06 | آزمون نرم‌افزار ST-35")
        print("کاربران (رمز همه: Pass1234!):")
        print("  prof.rezaei (استاد) | ta.karimi (دستیار) | student.sara / student.amir (دانشجو)")
        print("  edu.admin (مدیر آموزشی) | quality.expert (کیفیت) | tech.admin (مدیر فنی)")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
