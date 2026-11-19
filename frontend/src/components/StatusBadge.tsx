/** نشان وضعیت با متن فارسی — رنگ هرگز به‌تنهایی معنا نمی‌دهد. */

const STATUS_LABELS: Record<string, string> = {
  // وضعیت محتوا
  DRAFT: 'پیش‌نویس',
  GENERATING: 'در حال تولید',
  GENERATED: 'تولیدشده',
  UNDER_REVIEW: 'در حال بررسی',
  APPROVED: 'تأییدشده',
  PUBLISHED: 'منتشرشده',
  ARCHIVED: 'بایگانی‌شده',
  FAILED: 'ناموفق',
  NEEDS_REVISION: 'نیازمند اصلاح',
  WITHDRAWN: 'پس‌گرفته‌شده',
  // وضعیت Job
  QUEUED: 'در صف',
  RUNNING: 'در حال اجرا',
  SUCCEEDED: 'موفق',
  CANCELLED: 'لغوشده',
  // تسلط
  KNOWN: 'مسلط',
  PARTIAL: 'تسلط جزئی',
  WEAK: 'ضعیف',
  UNKNOWN: 'نامشخص',
  // سرفصل
  APPROVED_SYLLABUS: 'مصوب',
  // فعالیت برنامه مطالعه
  PROPOSED: 'پیشنهادی',
  ACCEPTED: 'پذیرفته‌شده',
  DONE: 'انجام‌شده',
  DISMISSED: 'ردشده',
  // طرح محتوا
  CONFIRMED: 'تأییدشده',
  PENDING: 'در انتظار',
  // ارزیابی
  IN_PROGRESS: 'در حال انجام',
  SUBMITTED: 'ارسال‌شده',
  GRADED: 'نمره‌داده‌شده',
  ACTIVE: 'فعال',
  // QC
  PASS: 'بدون اشکال',
  WARN: 'با هشدار',
  FAIL: 'نامنطبق',
  // مفهوم
  NOT_EXECUTED: 'اجرا نشده',
  AUTO: 'خودکار',
  AI_SUGGESTED: 'پیشنهاد AI',
  HUMAN: 'انسانی',
}

const TONES: Record<string, string> = {
  PUBLISHED: 'success',
  APPROVED: 'info',
  APPROVED_SYLLABUS: 'success',
  DRAFT: 'neutral',
  GENERATING: 'warn',
  GENERATED: 'info',
  UNDER_REVIEW: 'warn',
  ARCHIVED: 'neutral',
  FAILED: 'danger',
  NEEDS_REVISION: 'danger',
  WITHDRAWN: 'neutral',
  QUEUED: 'neutral',
  RUNNING: 'warn',
  SUCCEEDED: 'success',
  CANCELLED: 'neutral',
  KNOWN: 'success',
  PARTIAL: 'warn',
  WEAK: 'danger',
  UNKNOWN: 'neutral',
  PROPOSED: 'neutral',
  ACCEPTED: 'info',
  DONE: 'success',
  DISMISSED: 'neutral',
  CONFIRMED: 'info',
  PENDING: 'warn',
  IN_PROGRESS: 'warn',
  SUBMITTED: 'info',
  GRADED: 'success',
  ACTIVE: 'success',
  PASS: 'success',
  WARN: 'warn',
  FAIL: 'danger',
  NOT_EXECUTED: 'neutral',
  AUTO: 'info',
  AI_SUGGESTED: 'ai',
  HUMAN: 'success',
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status
}

export default function StatusBadge({ status, tone }: { status: string; tone?: string }) {
  const resolvedTone = tone || TONES[status] || 'neutral'
  return <span className={`badge badge-${resolvedTone}`}>{statusLabel(status)}</span>
}

/** نشان «تخمین AI» — برای هر مقدارِ محاسبه‌شده توسط هوش مصنوعی. */
export function AIEstimateBadge({ label = 'تخمین AI' }: { label?: string }) {
  return <span className="badge badge-ai">◈ {label}</span>
}

/** نشان «تأیید استاد» — برای مقادیر مصوب انسانی. */
export function HumanApprovedBadge({ label = 'تأیید استاد' }: { label?: string }) {
  return <span className="badge badge-success">✓ {label}</span>
}

/** نام فارسی نقش‌ها. */
export function roleLabel(role: string): string {
  const map: Record<string, string> = {
    STUDENT: 'دانشجو',
    PROFESSOR: 'استاد',
    ASSISTANT: 'دستیار آموزشی',
    GROUP_ADMIN: 'مدیر گروه',
    EDUCATION_ADMIN: 'مدیر آموزشی',
    QUALITY_REVIEWER: 'کارشناس کیفیت',
    TECH_ADMIN: 'مدیر فنی',
  }
  return map[role] || role
}

/** برچسب فارسی هدف محتوا / سبک / نوع آزمون و ... */
export function kindLabel(key: string): string {
  const map: Record<string, string> = {
    INTRO: 'معرفی',
    CONCEPT_TEACHING: 'آموزش مفهوم',
    PROBLEM_SOLVING: 'حل مسئله',
    REVIEW: 'مرور',
    PRACTICE: 'تمرین',
    ACADEMIC: 'دانشگاهی',
    APPLIED: 'کاربردی',
    EXAMPLE_BASED: 'مثال‌محور',
    STEPWISE: 'گام‌به‌گام',
    QUIZ: 'مینی‌آزمون',
    EXAM: 'آزمون اصلی',
    FIXED: 'ثابت',
    ADAPTIVE_PRACTICE: 'تمرین تطبیقی',
    STUDY: 'مطالعه',
    DIAGNOSTIC: 'تشخیصی',
    IMMEDIATE: 'بازخورد فوری',
    AFTER_FINISH: 'بازخورد پس از پایان',
    NONE: 'بدون بازخورد',
    FA: 'فارسی',
    EN: 'انگلیسی',
    FA_EN: 'دوزبانه',
  }
  return map[key] || key
}

/** برچسب فارسی نوع فرضیه تشخیصی. */
export function hypothesisLabel(key: string): string {
  const map: Record<string, string> = {
    CURRENT_WEAK: 'ضعف فعلی در مفهوم',
    PREREQ_WEAK: 'ضعف در پیش‌نیاز',
    MISCONCEPTION: 'بدفهمی رایج',
    SOLUTION_METHOD: 'مشکل در روش حل',
    CALCULATION_ERROR: 'خطای محاسبه‌ای',
    COMPREHENSION: 'مشکل درک مطلب',
    INSUFFICIENT_EVIDENCE: 'شواهد ناکافی',
  }
  return map[key] || key
}
