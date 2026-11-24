"""وارد کردن همه مدل‌ها برای metadata کامل (create_all و Alembic)."""
from app.models.identity import User, CourseRole
from app.models.courses import Course, CourseOffering, Enrollment
from app.models.syllabus import SyllabusVersion, SyllabusTopic, LearningObjective
from app.models.concepts import Concept, ConceptRelation, TopicConcept, ConceptMisconception
from app.models.resources import Resource, ResourceChunk, ResourcePermission
from app.models.content import ContentDocument, ContentPlan, ContentVersion, ContentReview
from app.models.exports import ExportJob, ExportArtifact
from app.models.questions import Question, QuestionVersion, QuestionConcept
from app.models.assessment import (
    Assessment, Attempt, Response, GradingReview, ResponseDispute,
)
from app.models.learning import LearningEvent, MasteryEstimate, DiagnosticHypothesis
from app.models.planning import StudyPlan, StudyActivity, ReviewSchedule
from app.models.tutor import TutorSession, TutorMessage
from app.models.collaboration import StudentCreation, PeerReview, ModerationReview
from app.models.ops import AIRun, JobRun, AuditLog, OutboxEvent
from app.models.journey import (ReferenceSyncLog, StuckMark, ErrorNotebookEntry,
                                TeachBackSubmission, LearningSession, ExamPrepPlan,
                                MasterdataSyncLog, PayehyarRecord, PayehyarEventInbox)

__all__ = [
    "User", "CourseRole",
    "Course", "CourseOffering", "Enrollment",
    "SyllabusVersion", "SyllabusTopic", "LearningObjective",
    "Concept", "ConceptRelation", "TopicConcept", "ConceptMisconception",
    "Resource", "ResourceChunk", "ResourcePermission",
    "ContentDocument", "ContentPlan", "ContentVersion", "ContentReview",
    "ExportJob", "ExportArtifact",
    "Question", "QuestionVersion", "QuestionConcept",
    "Assessment", "Attempt", "Response", "GradingReview", "ResponseDispute",
    "LearningEvent", "MasteryEstimate", "DiagnosticHypothesis",
    "StudyPlan", "StudyActivity", "ReviewSchedule",
    "TutorSession", "TutorMessage",
    "StudentCreation", "PeerReview", "ModerationReview",
    "AIRun", "JobRun", "AuditLog", "OutboxEvent",
    "ReferenceSyncLog", "StuckMark", "ErrorNotebookEntry",
    "TeachBackSubmission", "LearningSession", "ExamPrepPlan", "MasterdataSyncLog",
    "PayehyarRecord", "PayehyarEventInbox",
]
