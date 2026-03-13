"""Initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=True),
        sa.Column("secret_key", sa.LargeBinary(), nullable=True),
        sa.Column("join_code", sa.String(length=64), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("join_code"),
    )
    op.create_index(op.f("ix_schools_join_code"), "schools", ["join_code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.LargeBinary(), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.LargeBinary(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "email_hash", name="uq_users_school_email_hash"),
    )
    op.create_index(op.f("ix_users_email_hash"), "users", ["email_hash"], unique=False)
    op.create_index(op.f("ix_users_school_id"), "users", ["school_id"], unique=False)

    op.create_table(
        "classrooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("grade_level", sa.String(length=32), nullable=True),
        sa.Column("academic_year", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_classrooms_school_id"), "classrooms", ["school_id"], unique=False)
    op.create_index(op.f("ix_classrooms_teacher_id"), "classrooms", ["teacher_id"], unique=False)

    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("week_of", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assessments_classroom_id"), "assessments", ["classroom_id"], unique=False)
    op.create_index(op.f("ix_assessments_school_id"), "assessments", ["school_id"], unique=False)

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=False),
        sa.Column("max_points", sa.Float(), nullable=False),
        sa.Column("standards", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("dok_level", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "question_number", name="uq_question_number_per_assessment"),
    )
    op.create_index(op.f("ix_questions_assessment_id"), "questions", ["assessment_id"], unique=False)

    op.create_table(
        "student_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_xid", sa.String(length=128), nullable=False),
        sa.Column("points_earned", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "question_id", "student_xid", name="uq_student_question_score"),
    )
    op.create_index(op.f("ix_student_scores_assessment_id"), "student_scores", ["assessment_id"], unique=False)
    op.create_index(op.f("ix_student_scores_question_id"), "student_scores", ["question_id"], unique=False)
    op.create_index(op.f("ix_student_scores_student_xid"), "student_scores", ["student_xid"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=128), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_school_id"), "audit_logs", ["school_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_school_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index(op.f("ix_student_scores_student_xid"), table_name="student_scores")
    op.drop_index(op.f("ix_student_scores_question_id"), table_name="student_scores")
    op.drop_index(op.f("ix_student_scores_assessment_id"), table_name="student_scores")
    op.drop_table("student_scores")

    op.drop_index(op.f("ix_questions_assessment_id"), table_name="questions")
    op.drop_table("questions")

    op.drop_index(op.f("ix_assessments_school_id"), table_name="assessments")
    op.drop_index(op.f("ix_assessments_classroom_id"), table_name="assessments")
    op.drop_table("assessments")

    op.drop_index(op.f("ix_classrooms_teacher_id"), table_name="classrooms")
    op.drop_index(op.f("ix_classrooms_school_id"), table_name="classrooms")
    op.drop_table("classrooms")

    op.drop_index(op.f("ix_users_school_id"), table_name="users")
    op.drop_index(op.f("ix_users_email_hash"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_schools_join_code"), table_name="schools")
    op.drop_table("schools")
