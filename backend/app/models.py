from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .database import Base


# ============================================================
# Course
# ============================================================

class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        server_default="1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    topics: Mapped[list[CourseTopic]] = relationship(
        "CourseTopic",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    quizzes: Mapped[list[Quiz]] = relationship(
        "Quiz",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ============================================================
# CourseTopic
# ============================================================

class CourseTopic(Base):
    __tablename__ = "course_topics"

    __table_args__ = (
        Index(
            "ix_course_topics_course_id_sort_order",
            "course_id",
            "sort_order",
        ),
        CheckConstraint(
            "session_minute > 0",
            name="ck_course_topics_session_minute_positive",
        ),
        CheckConstraint(
            "sort_order > 0",
            name="ck_course_topics_sort_order_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "courses.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    session_minute: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
        server_default="50",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        server_default="1",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        server_default="1",
    )

    course: Mapped[Course] = relationship(
        "Course",
        back_populates="topics",
    )

    contents: Mapped[list[EducationalContent]] = relationship(
        "EducationalContent",
        back_populates="topic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    quizzes: Mapped[list[Quiz]] = relationship(
        "Quiz",
        back_populates="topic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ============================================================
# EducationalContent
# ============================================================

class EducationalContent(Base):
    __tablename__ = "educational_contents"

    __table_args__ = (
        Index(
            "ix_educational_contents_topic_id_created_at",
            "topic_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    topic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "course_topics.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="ai",
        nullable=False,
        server_default="ai",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    topic: Mapped[CourseTopic] = relationship(
        "CourseTopic",
        back_populates="contents",
    )

    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ============================================================
# Quiz
# ============================================================

class Quiz(Base):
    __tablename__ = "quizzes"

    __table_args__ = (
        Index(
            "ix_quizzes_course_id_topic_id",
            "course_id",
            "topic_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "courses.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    topic_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "course_topics.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    course: Mapped[Course] = relationship(
        "Course",
        back_populates="quizzes",
    )

    topic: Mapped[CourseTopic | None] = relationship(
        "CourseTopic",
        back_populates="quizzes",
    )

    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    attempts: Mapped[list[QuizAttempt]] = relationship(
        "QuizAttempt",
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ============================================================
# Question
# ============================================================

class Question(Base):
    __tablename__ = "questions"

    __table_args__ = (
        CheckConstraint(
            "question_type IN ('multiple_choice', 'essay')",
            name="ck_questions_question_type",
        ),
        CheckConstraint(
            "correct_option IN ('A', 'B', 'C', 'D') OR correct_option IS NULL",
            name="ck_questions_correct_option",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    quiz_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quizzes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    content_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "educational_contents.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    question_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="multiple_choice",
        server_default="multiple_choice",
    )

    option_a: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    option_b: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    option_c: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    option_d: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    correct_option: Mapped[str | None] = mapped_column(
        String(1),
        nullable=True,
    )

    model_answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    quiz: Mapped[Quiz] = relationship(
        "Quiz",
        back_populates="questions",
    )

    content: Mapped[EducationalContent | None] = relationship(
        "EducationalContent",
        back_populates="questions",
    )


# ============================================================
# QuizAttempt
# ============================================================

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    quiz_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quizzes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    student_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    correct_answers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    total_questions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    essay_answers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    pending_essay_review: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="0",
    )

    answers_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    quiz: Mapped[Quiz] = relationship(
        "Quiz",
        back_populates="attempts",
    )


# ============================================================
# AI Service Usage (آمار استفاده از سرویس‌های هوش مصنوعی)
# ============================================================

class AIServiceUsage(Base):
    __tablename__ = "ai_service_usage"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    request_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    request_timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        server_default="1",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    request_duration_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    topic_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    question_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

# ============================================================
# User — کاربران سامانه (مدیرگروه / استاد / دانشجو)
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # admin | group_manager | professor | student
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="student",
        server_default="student",
        index=True,
    )

    # pending | active | rejected | disabled
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    approved_by_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
