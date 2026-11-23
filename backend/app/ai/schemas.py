"""خروجی‌های ساختاریافته مدل — با Pydantic اعتبارسنجی می‌شوند (بخش ۱۴.۲)."""
from pydantic import BaseModel, Field


class PlanSection(BaseModel):
    block_type: str
    concept_keys: list[str] = Field(default_factory=list)
    minutes: int = 10
    notes: str = ""


class ContentPlanOut(BaseModel):
    title: str
    learning_objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    sections_order: list[PlanSection] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    timing_summary: str = ""
    assessment_method: str = ""


class AIBlock(BaseModel):
    id: str | None = None
    type: str
    title: str | None = None
    body: str | None = None
    items: list[str] | None = None
    steps: list[str] | None = None
    columns: list[str] | None = None
    rows: list[list] | None = None
    formula: str | None = None
    language: str | None = None
    question: str | None = None
    answer: str | None = None
    explanation: str | None = None
    concept_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class ContentOut(BaseModel):
    title: str
    blocks: list[AIBlock]


class BlockRegenOut(BaseModel):
    block: AIBlock


class AIQuestion(BaseModel):
    type: str
    body: str
    options: list[dict] | None = None
    answer: dict = Field(default_factory=dict)
    explanation: str = ""
    difficulty: str = "MEDIUM"
    cognitive_level: str = "UNDERSTAND"
    concept_key: str = ""
    misconception: str | None = None


class QuestionsOut(BaseModel):
    questions: list[AIQuestion]


class SyllabusChapter(BaseModel):
    title: str
    topics: list[str] = Field(default_factory=list)
    hours: float | None = None


class SyllabusStructureOut(BaseModel):
    chapters: list[SyllabusChapter] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    ambiguous: list[str] = Field(default_factory=list)


class RubricScore(BaseModel):
    criterion: str
    score: float
    max_score: float
    evidence: str = ""


class EssayGradeOut(BaseModel):
    rubric_scores: list[RubricScore] = Field(default_factory=list)
    total_score: float
    max_total: float
    uncertainty: str = "MEDIUM"
    rationale: str = ""


class ShortAnswerCheckOut(BaseModel):
    correct: bool
    confidence: str = "LOW"
    rationale: str = ""


class TutorCitation(BaseModel):
    resource_id: str
    locator: str = ""
    quote: str = ""


class TutorOut(BaseModel):
    answer: str
    citations: list[TutorCitation] = Field(default_factory=list)
    insufficient_evidence: bool = False
    needs_teacher: bool = False
    help_mode: str | None = None      # EXPLAIN/GUIDE/PRACTICE — نردبان راهنمایی
    ladder_level: int | None = None   # 1 سؤال راهنما … 5 راه‌حل کامل


class TeachBackCriterion(BaseModel):
    criterion: str
    score: float
    max_score: float
    evidence: str = ""


class TeachBackFeedbackOut(BaseModel):
    rubric_scores: list[TeachBackCriterion] = Field(default_factory=list)
    follow_up_question: str = ""
    gaps: list[str] = Field(default_factory=list)
    encouragement: str = ""


class CreationFeedbackOut(BaseModel):
    feedback: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    approved_for_peer: bool = False
