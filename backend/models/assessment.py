import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classrooms.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    week_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    classroom = relationship("Classroom", back_populates="assessments")
    questions = relationship("Question", back_populates="assessment", cascade="all, delete-orphan")
    student_scores = relationship("StudentScore", back_populates="assessment", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("assessment_id", "question_number", name="uq_question_number_per_assessment"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    max_points: Mapped[float] = mapped_column(Float, nullable=False)
    standards: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, nullable=False)
    dok_level: Mapped[str | None] = mapped_column(String(32), nullable=True)

    assessment = relationship("Assessment", back_populates="questions")
    student_scores = relationship("StudentScore", back_populates="question", cascade="all, delete-orphan")


class StudentScore(Base):
    __tablename__ = "student_scores"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "question_id",
            "student_xid",
            name="uq_student_question_score",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    student_xid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    points_earned: Mapped[float] = mapped_column(Float, nullable=False)

    assessment = relationship("Assessment", back_populates="student_scores")
    question = relationship("Question", back_populates="student_scores")
