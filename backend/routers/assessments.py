"""
Assessment router: upload/list/sample-load endpoints.
All operations are tenant-scoped to the authenticated user's school.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_active_teacher
from models.assessment import Assessment, Question, StudentScore
from models.school import Classroom
from models.user import User
from services.csv_ingestion import parse_metadata_csv, parse_reveal_assessment_csv

router = APIRouter()

SAMPLE_DIR = Path("/app/sample_data")
SAMPLE_ASSESSMENT = SAMPLE_DIR / "sample_assessment.csv"
SAMPLE_METADATA = SAMPLE_DIR / "sample_metadata.csv"


def _is_admin(user: User) -> bool:
    return user.role in ("school_admin", "super_admin")


def _extract_score_columns(scores_df: pd.DataFrame) -> dict[int, str]:
    score_cols: dict[int, str] = {}
    for col in scores_df.columns:
        match = re.match(r"Q(\d+)\s*\(", str(col))
        if not match:
            continue
        score_cols[int(match.group(1))] = str(col)
    return score_cols


def _to_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


async def _get_target_classroom(
    db: AsyncSession,
    current_user: User,
    classroom_id: UUID | None,
) -> Classroom:
    if classroom_id:
        conditions = [
            Classroom.id == classroom_id,
            Classroom.school_id == current_user.school_id,
            Classroom.is_active == True,
        ]
        if not _is_admin(current_user):
            conditions.append(Classroom.teacher_id == current_user.id)

        result = await db.execute(select(Classroom).where(*conditions))
        classroom = result.scalar_one_or_none()
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        return classroom

    conditions = [
        Classroom.school_id == current_user.school_id,
        Classroom.is_active == True,
    ]
    if not _is_admin(current_user):
        conditions.append(Classroom.teacher_id == current_user.id)

    result = await db.execute(
        select(Classroom)
        .where(*conditions)
        .order_by(Classroom.name.asc())
        .limit(1)
    )
    classroom = result.scalar_one_or_none()
    if not classroom:
        classroom = Classroom(
            school_id=current_user.school_id,
            teacher_id=current_user.id,
            name="My Classroom",
            grade_level=None,
            academic_year=None,
            is_active=True,
        )
        db.add(classroom)
        await db.flush()
    return classroom


async def _persist_assessment(
    db: AsyncSession,
    current_user: User,
    classroom: Classroom,
    scores_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    assessment_name: str,
    week_of: date | None,
) -> tuple[Assessment, int, int]:
    score_cols = _extract_score_columns(scores_df)
    if not score_cols:
        raise HTTPException(status_code=400, detail="No score columns found in assessment file")

    assessment = Assessment(
        school_id=current_user.school_id,
        classroom_id=classroom.id,
        name=assessment_name,
        week_of=week_of,
    )
    db.add(assessment)
    await db.flush()

    question_ids: dict[int, UUID] = {}
    for _, row in metadata_df.iterrows():
        q_num = int(row["question_number"])
        if q_num not in score_cols:
            continue

        standards_raw = str(row.get("standards", ""))
        standards = [s.strip() for s in standards_raw.split(",") if s.strip()]
        question = Question(
            assessment_id=assessment.id,
            question_number=q_num,
            question_type=str(row.get("question_type", "unknown"))[:64],
            max_points=float(row.get("max_points", 1.0) or 1.0),
            standards=standards,
            dok_level=str(row.get("dok_level", "") or "")[:32] or None,
        )
        db.add(question)
        await db.flush()
        question_ids[q_num] = question.id

    if not question_ids:
        raise HTTPException(
            status_code=400,
            detail="Metadata did not match any assessment question columns",
        )

    inserted_scores = 0
    for _, row in scores_df.iterrows():
        student_xid = str(row.get("student_xid", "")).strip()
        if not student_xid:
            continue

        for q_num, col_name in score_cols.items():
            question_id = question_ids.get(q_num)
            if not question_id:
                continue

            points = _to_float(row.get(col_name))
            if points is None:
                continue

            db.add(
                StudentScore(
                    assessment_id=assessment.id,
                    question_id=question_id,
                    student_xid=student_xid,
                    points_earned=points,
                )
            )
            inserted_scores += 1

    if inserted_scores == 0:
        raise HTTPException(status_code=400, detail="No student scores found to import")

    return assessment, len(question_ids), inserted_scores


@router.get("")
async def list_assessments(
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    query = select(Assessment).where(Assessment.school_id == current_user.school_id)

    if not _is_admin(current_user):
        classroom_ids_result = await db.execute(
            select(Classroom.id).where(
                Classroom.school_id == current_user.school_id,
                Classroom.teacher_id == current_user.id,
                Classroom.is_active == True,
            )
        )
        classroom_ids = list(classroom_ids_result.scalars().all())
        if not classroom_ids:
            return []
        query = query.where(Assessment.classroom_id.in_(classroom_ids))

    result = await db.execute(query.order_by(Assessment.created_at.desc()))
    assessments = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "name": item.name,
            "classroom_id": str(item.classroom_id) if item.classroom_id else None,
            "week_of": item.week_of.isoformat() if item.week_of else None,
            "created_at": item.created_at.isoformat(),
        }
        for item in assessments
    ]


@router.get("/classrooms/mine")
async def list_my_classrooms(
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    conditions = [
        Classroom.school_id == current_user.school_id,
        Classroom.is_active == True,
    ]
    if not _is_admin(current_user):
        conditions.append(Classroom.teacher_id == current_user.id)

    result = await db.execute(select(Classroom).where(*conditions).order_by(Classroom.name.asc()))
    classrooms = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "name": item.name,
            "grade_level": item.grade_level,
            "academic_year": item.academic_year,
        }
        for item in classrooms
    ]


@router.post("/upload/math", status_code=status.HTTP_201_CREATED)
async def upload_math_assessment(
    math_csv: UploadFile = File(...),
    metadata_csv: UploadFile = File(...),
    classroom_id: UUID | None = Form(None),
    assessment_name: str | None = Form(None),
    week_of: date | None = Form(None),
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    classroom = await _get_target_classroom(db, current_user, classroom_id)

    scores_df, score_warnings = parse_reveal_assessment_csv(await math_csv.read())
    metadata_df, metadata_warnings = parse_metadata_csv(await metadata_csv.read())

    title = assessment_name.strip() if assessment_name else f"Math Assessment {date.today().isoformat()}"
    assessment, question_count, score_count = await _persist_assessment(
        db=db,
        current_user=current_user,
        classroom=classroom,
        scores_df=scores_df,
        metadata_df=metadata_df,
        assessment_name=title,
        week_of=week_of,
    )

    return {
        "assessment_id": str(assessment.id),
        "name": assessment.name,
        "classroom_id": str(classroom.id),
        "questions_imported": question_count,
        "scores_imported": score_count,
        "warnings": [*score_warnings, *metadata_warnings],
    }


@router.post("/load-sample", status_code=status.HTTP_201_CREATED)
async def load_sample_assessment(
    classroom_id: UUID | None = None,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    if not SAMPLE_ASSESSMENT.exists() or not SAMPLE_METADATA.exists():
        raise HTTPException(
            status_code=500,
            detail="Sample files not found in /app/sample_data",
        )

    classroom = await _get_target_classroom(db, current_user, classroom_id)

    scores_df, score_warnings = parse_reveal_assessment_csv(SAMPLE_ASSESSMENT.read_bytes())
    metadata_df, metadata_warnings = parse_metadata_csv(SAMPLE_METADATA.read_bytes())

    assessment, question_count, score_count = await _persist_assessment(
        db=db,
        current_user=current_user,
        classroom=classroom,
        scores_df=scores_df,
        metadata_df=metadata_df,
        assessment_name=f"Sample Maryland Math {date.today().isoformat()}",
        week_of=date.today(),
    )

    return {
        "assessment_id": str(assessment.id),
        "name": assessment.name,
        "classroom_id": str(classroom.id),
        "questions_imported": question_count,
        "scores_imported": score_count,
        "warnings": [*score_warnings, *metadata_warnings],
    }
