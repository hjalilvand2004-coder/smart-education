# قرارداد API سامانه یادگیری هوشمند دانشجو۳۶۰ (نسخه v1)

این سند، قرارداد ثابت ارتباط بک‌اند (FastAPI) و فرانت‌اند (React) است.
هر دو سمت موظف به رعایت دقیق همین شکل‌ها هستند.

## قواعد عمومی

- مسیر پایه: `/api/v1`
- احراز هویت: هدر `Authorization: Bearer <JWT>`
- خطای استاندارد:
```json
{ "error": { "code": "FORBIDDEN", "message": "...", "details": {}, "request_id": "uuid" } }
```
- کدهای خطا: `VALIDATION_ERROR`(422), `UNAUTHORIZED`(401), `FORBIDDEN`(403), `NOT_FOUND`(404), `CONFLICT`(409), `RATE_LIMITED`(429), `INTERNAL`(500)
- صفحه‌بندی: `?page=1&page_size=20` → `{ "items": [...], "total": 0, "page": 1, "page_size": 20 }`
- Jobهای طولانی: پاسخ `202 Accepted` با `{ "job_id": "uuid", "status": "QUEUED" }` و پیگیری با `GET /jobs/{id}`
- Idempotency: هدر `Idempotency-Key` در عملیات حساس (تولید محتوا، تولید سؤال، خروجی گرفتن)
- تاريخ/زمان: ISO-8601 UTC (مثلاً `2026-11-17T12:00:00Z`)

## ساختارهای پایه

```ts
Role = "STUDENT" | "PROFESSOR" | "ASSISTANT" | "GROUP_ADMIN" | "EDUCATION_ADMIN" | "QUALITY_REVIEWER" | "TECH_ADMIN"
JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED"
ContentStatus = "DRAFT" | "GENERATING" | "GENERATED" | "UNDER_REVIEW" | "APPROVED" | "PUBLISHED" | "ARCHIVED" | "FAILED" | "NEEDS_REVISION" | "WITHDRAWN"
QuestionType = "MCQ" | "MULTI_SELECT" | "TRUE_FALSE" | "SHORT_ANSWER" | "ESSAY" | "NUMERIC" | "CASE" | "CODE" | "ORDERING" | "MATCHING"
```

---

## ۱. احراز هویت و پروفایل

| روش | مسیر | توضیح |
|---|---|---|
| POST | `/auth/login` | بدنه `{username, password}` → `{access_token, token_type:"bearer", user}` |
| GET | `/me` | پروفایل کاربر: `{id, username, full_name, role, course_roles:[{course_id, course_title, role}]}` |

## ۲. درس‌ها، سرفصل و گراف مفاهیم

| روش | مسیر | توضیح |
|---|---|---|
| GET | `/courses` | درس‌های کاربر (با نقش هر درس): `[{id, code, title, department, term, my_role, enrollments_count?}]` |
| GET | `/courses/{course_id}` | جزئیات درس + نسخه سرفصل فعال |
| GET | `/courses/{course_id}/syllabus` | سرفصل مجاز: `{id, version_number, status, title, approved_at, chapters:[{id, title, suggested_hours, topics:[{id,title,suggested_hours, concepts:[{id,name}], objectives:[{id,code,statement}]}]}], objectives:[...]}` |
| GET | `/courses/{course_id}/syllabus/versions` | (کارکنان) فهرست نسخه‌ها با وضعیت |
| POST | `/syllabus-imports` | (کارکنان) بدنه `{course_id, source_kind:"TEXT"|"DOCX"|"PDF", text?, file?}` (multipart) → 202 job |
| GET | `/syllabus-versions/{id}` | سرفصل کامل (کارکنان) |
| POST | `/syllabus-versions/{id}/approve` | `{notes?}` → تأیید (PROFESSOR/GROUP_ADMIN/EDUCATION_ADMIN) |
| GET | `/syllabus-versions/{id}/diff?against={id2}` | تفاوت دو نسخه: `{added_topics, removed_topics, changed_topics:[{id, field, before, after}], added_objectives, removed_objectives}` |
| GET | `/courses/{course_id}/concept-graph` | `{nodes:[{id,name,status,topic_ids:[], mastery?}], edges:[{from,to,type}]}` — نوع: `PREREQUISITE_OF\|PART_OF\|RELATED_TO\|APPLIED_IN\|MISCONCEPTION_OF` |
| POST | `/courses/{course_id}/concepts` | (کارکنان) `{name, description, topic_ids?, prerequisites?:[concept_id], misconceptions?:[string]}` |
| PATCH | `/concepts/{id}` | ویرایش مفهوم (کارکنان) |

## ۳. استودیوی محتوا (استاد/دستیار)

| روش | مسیر | توضیح |
|---|---|---|
| GET | `/content-documents?course_id=` | فهرست اسناد (کارکنان؛ وضعیت هر سند و آخرین نسخه) |
| POST | `/content-documents` | `{course_id, syllabus_version_id, title, goal:"INTRO\|CONCEPT_TEACHING\|PROBLEM_SOLVING\|REVIEW\|PRACTICE", scope:{topic_ids:[], concept_ids:[]}, audience_level, duration_minutes, language:"FA\|EN\|FA_EN", style:"ACADEMIC\|APPLIED\|EXAMPLE_BASED\|STEPWISE", components:["definition","example","exercise","diagram","summary","references"], source_resource_ids:[], constraints?}` → سند DRAFT |
| POST | `/content-documents/{id}/generation-jobs` | `{mode:"PLAN"\|"CONTENT"\|"FULL", auto_confirm?:bool, block_id?(بازتولید یک بخش), instruction?(دستور بازتولید)} + هدر Idempotency-Key` → 202 |
| GET | `/content-documents/{id}` | سند + نسخه‌ها + طرح فعال |
| GET | `/content-versions/{id}` | `{id, status, revision, blocks:[Block], qc_report, plan, coverage, human_changes:[{block_id, at, by}], generated_by:"AI\|HUMAN"}` |
| PATCH | `/content-versions/{id}/blocks/{block_id}` | `{patch:{...}, expected_revision}` → 409 در صورت تداخل (CONFLICT) |
| POST | `/content-versions/{id}/blocks/{block_id}/regenerate` | `{instruction?}` → 202 job؛ فقط همان بلوک بازتولید می‌شود |
| POST | `/content-versions/{id}/reviews` | `{decision:"APPROVE"\|"REQUEST_CHANGES", notes}` |
| POST | `/content-versions/{id}/publish` | انتشار (فقط PROFESSOR همان درس) |
| POST | `/content-versions/{id}/exports` | `{format:"PDF"\|"PPTX"\|"HTML"\|"DOCX", options?}` + Idempotency-Key → 202 |

**Block** (بلوک محتوایی):
```ts
type Block = { id: string, type: "heading"|"text"|"definition"|"note"|"worked_example"|"exercise"|"table"|"formula"|"image"|"code"|"self_check"|"summary"|"reference", title?, body?, items?, steps?, columns?, rows?, formula?, language?, question?, answer?, explanation?, concept_ids?: string[], source_refs?: string[] }
```

**QC report**: `{coverage:[{objective_id, covered, evidence_blocks}], out_of_scope_concepts:[], missing_sources:[], invalid_refs:[], structure_warnings:[], overall:"PASS"|"WARN"|"FAIL"}`

## ۴. بانک سؤال

| روش | مسیر | توضیح |
|---|---|---|
| GET | `/questions?course_id=&status=&type=&concept_id=` | فهرست سؤال‌ها (کارکنان) |
| POST | `/questions` | ساخت دستی سؤال (کارکنان) — ساختار مثل QuestionVersion |
| POST | `/question-generation-jobs` | `{course_id, syllabus_version_id, concept_ids:[], types:[], count, difficulty:"EASY"\|"MEDIUM"\|"HARD", usage:"PRACTICE"\|"QUIZ"\|"OFFICIAL_EXAM"}` → 202 |
| GET | `/questions/{id}` | `{id, type, difficulty_estimated, difficulty_empirical?, cognitive_level, status, versions:[QuestionVersion], concepts:[], misconception?, usage}` |
| POST | `/questions/{id}/reviews` | `{decision:"APPROVE"\|"REJECT", notes}` |

**QuestionVersion**: `{id, version_number, body, options?:[{key,text,is_correct?}], answer, explanation, rubric?, source_refs:[], is_current}`

## ۵. ارزیابی و آزمون

| روش | مسیر | توضیح |
|---|---|---|
| POST | `/assessments` | (PROFESSOR/ASSISTANT) `{course_id, offering_id?, title, kind:"QUIZ"\|"PRACTICE"\|"EXAM", mode:"FIXED"\|"ADAPTIVE_PRACTICE", blueprint:{sections:[{concept_ids:[], count, difficulty}]}, policy:{feedback:"IMMEDIATE"\|"AFTER_FINISH"\|"NONE", allow_hint:bool, shuffle:bool}, duration_minutes?}` |
| GET | `/assessments?course_id=` | فهرست ارزیابی‌ها |
| POST | `/assessments/{id}/attempts` | (دانشجوی ثبت‌نام‌شده) → `{id, status:"IN_PROGRESS", questions:[QuestionForStudent]}` |
| GET | `/attempts/{id}` | وضعیت تلاش + سؤال‌های پاسخ‌داده/باقی‌مانده (در حالت تطبیقی ممکن است فهرست تغییر کند) |
| POST | `/attempts/{id}/responses` | `{question_version_id, answer, time_spent_ms?, hint_used?}` → `{auto_scored, score?, ai_feedback?}` |
| POST | `/attempts/{id}/finish` | → `{score, max_score, per_concept:[{concept_id, correct, total}]}` |
| GET | `/responses/{id}` | نتیجه کامل: `{score, final_score?, grading:"AUTO"\|"AI_SUGGESTED"\|"HUMAN", ai_feedback?, rubric_scores?}` |
| POST | `/responses/{id}/grading-reviews` | (استاد) `{scores:[{criterion, score}], final_score, comment}` — نمره رسمی انسانی |
| POST | `/responses/{id}/disputes` | (دانشجو) `{comment}` → ثبت اعتراض |
| GET | `/assessments/{id}/results` | (استاد) نتایج تجمیعی |

`QuestionForStudent` (بدون کلید): `{question_version_id, number, type, body, options?:[{key,text}], formula?, policy_help?}`

## ۶. مدل یادگیری و تحلیل

| روش | مسیر | توضیح |
|---|---|---|
| GET | `/me/courses/{course_id}/mastery` | `[ {concept_id, concept_name, estimated_mastery: 0..1|null, status:"KNOWN"\|"PARTIAL"\|"WEAK"\|"UNKNOWN", evidence_count, confidence, last_evidence_at, prerequisites:[{concept_id, status}] } ]` — UNKNOWN یعنی شواهد ناکافی (نه ضعف قطعی) |
| GET | `/me/courses/{course_id}/diagnostics` | `[ {concept_id, hypothesis_type:"CURRENT_WEAK"\|"PREREQ_WEAK"\|"MISCONCEPTION"\|"SOLUTION_METHOD"\|"CALCULATION_ERROR"\|"COMPREHENSION"\|"INSUFFICIENT_EVIDENCE", confidence, rationale, recommended_actions:[{type:"REVIEW"\|"PRACTICE"\|"DIAGNOSTIC_QUIZ"\|"ASK_TEACHER", title, target_id?, reason}] } ]` |
| GET | `/courses/{course_id}/mastery/aggregate` | (استاد) نقشه ضعف کلاس: `[ {concept_id, avg_mastery, weak_ratio, unknown_ratio, students_count, needs_reteach:bool} ]` |
| POST | `/learning-events` | `{course_id, type:"CONTENT_VIEWED", payload:{content_version_id, block_id?, dwell_ms?}}` |

## ۷. برنامه مطالعه و مرور

| روش | مسیر | توضیح |
|---|---|---|
| POST | `/study-plans` | `{course_id, exam_date?, weekly_hours, goals?, regenerate?:bool}` → `{id, activities:[StudyActivity], rationale_summary}` |
| GET | `/me/study-plans?course_id=` | آخرین برنامه |
| PATCH | `/study-activities/{id}` | `{status:"ACCEPTED"\|"DONE"\|"DISMISSED"}` |
| GET | `/me/review-schedule?course_id=` | `[ {concept_id, concept_name, due_at, interval_days, repetitions, ease} ]` |

**StudyActivity**: `{id, day_offset, date?, title, type:"REVIEW"\|"PRACTICE"\|"STUDY"\|"DIAGNOSTIC", concept_id?, concept_name?, resource_id?, estimated_minutes, rationale, status}`

## ۸. استاد هوشمند گفتگو‌محور

| روش | مسیر | توضیح |
|---|---|---|
| POST | `/tutor/sessions` | `{course_id, mode:"LEARNING"\|"ASSESSMENT", assessment_id?}` |
| GET | `/tutor/sessions/{id}/messages` | تاریخچه: `[ {id, role:"user"\|"assistant", content, citations?, created_at} ]` |
| POST | `/tutor/sessions/{id}/messages` | `{content, stream?:bool}` — بدون stream: پیام assistant کامل؛ با `stream:true`: پاسخ SSE با رویدادهای `token`، `citations`، `done` |
| POST | `/tutor/messages/{id}/report` | `{issue}` → گزارش پاسخ نادرست به استاد |

**Citation**: `{resource_id, resource_title, locator:"صفحه ۱۲، بخش ۳"\|..., quote}`

## ۹. یادگیری مشارکتی (دانشجو تولیدکننده)

| روش | مسیر | توضیح |
|---|---|---|
| POST | `/student-creations` | `{course_id, activity_type:"QUESTION_DESIGN"\|"EXPLANATION"\|"EXAMPLE"\|"CRITIQUE", concept_id?, content, ai_use_disclosed?:bool}` → بازخورد AI فوری |
| GET | `/student-creations?course_id=` | (دانشجو: موارد خودش / استاد: همه) |
| POST | `/student-creations/{id}/submit` | ارسال برای بررسی همتا/استاد |
| POST | `/student-creations/{id}/peer-reviews` | `{scores:{clarity, correctness, usefulness}, comment}` |
| POST | `/student-creations/{id}/teacher-reviews` | `{decision:"APPROVE"\|"REJECT", comment}` — هرگز ورود مستقیم به بانک رسمی |

## ۱۰. عملیات

| روش | مسیر | توضیح |
|---|---|---|
| GET | `/jobs/{id}` | `{id, kind, status, progress:0..100, steps:[{name, status, at}], error?, result?}` |
| GET | `/audit-logs?action=&entity_type=` | (EDUCATION_ADMIN/TECH_ADMIN) |
| GET | `/ai-runs` | (TECH_ADMIN/EDUCATION_ADMIN) مصرف مدل: `[ {id, purpose, provider, model, prompt_version, status, latency_ms, tokens_in, tokens_out, created_at} ]` |
| GET | `/exports/{id}/download` | دریافت فایل مجاز (کنترل دسترسی) |
