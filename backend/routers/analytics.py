"""
Analytics router: all proficiency and visualization endpoints.
All data is tenant-scoped to the authenticated user's school.
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.dependencies import get_current_active_teacher
from models.user import User
from models.assessment import Assessment, StudentScore, Question
from models.school import Classroom
from services.proficiency import calculate_proficiency
from services.root_cause import (
    analyze_story_vs_computation,
    calculate_literacy_correlation,
    build_intervention_groups,
)
import pandas as pd

router = APIRouter()


async def get_assessment_dataframes(
    assessment_id: UUID,
    school_id: UUID,
    db: AsyncSession,
):
    """Fetch assessment data and return as DataFrames. Enforces tenant scoping."""
    # Verify assessment belongs to this school
    assessment = await db.get(Assessment, assessment_id)
    if not assessment or assessment.school_id != school_id:
        return None, None

    # Fetch scores and questions
    scores_result = await db.execute(
        select(StudentScore, Question)
        .join(Question, StudentScore.question_id == Question.id)
        .where(StudentScore.assessment_id == assessment_id)
    )
    rows = scores_result.fetchall()

    if not rows:
        return None, None

    # Build scores DataFrame
    scores_data = {}
    questions_meta = {}

    for score, question in rows:
        xid = score.student_xid
        q_col = f"Q{question.question_number} ({question.max_points} point)"

        if xid not in scores_data:
            scores_data[xid] = {"student_xid": xid}
        scores_data[xid][q_col] = score.points_earned

        if question.question_number not in questions_meta:
            questions_meta[question.question_number] = {
                "question_number": question.question_number,
                "question_type": question.question_type,
                "max_points": float(question.max_points),
                "standards": ",".join(question.standards or []),
                "dok_level": question.dok_level,
            }

    scores_df = pd.DataFrame(list(scores_data.values()))
    metadata_df = pd.DataFrame(list(questions_meta.values()))

    return scores_df, metadata_df


@router.get("/proficiency_by_standard")
async def proficiency_by_standard(
    assessment_id: UUID,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Bar chart data: proficiency rate per CCSS standard, sorted ascending."""
    scores_df, metadata_df = await get_assessment_dataframes(
        assessment_id, current_user.school_id, db
    )
    if scores_df is None:
        return {"data": [], "suppressed": False}

    _, standard_results, _ = calculate_proficiency(scores_df, metadata_df)

    data = [
        {
            "standard": r.standard_code,
            "proficiency": round(r.avg_proficiency * 100, 1),
            "student_count": r.student_count,
            "suppressed": r.suppressed,
        }
        for r in standard_results
    ]
    return {"data": data, "chart_type": "bar"}


@router.get("/student_heatmap")
async def student_heatmap(
    assessment_id: UUID,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    Heatmap data: anonymized student vs standard proficiency matrix.
    Note: student XIDs returned here are already pseudonyms from the DB.
    """
    scores_df, metadata_df = await get_assessment_dataframes(
        assessment_id, current_user.school_id, db
    )
    if scores_df is None:
        return {"data": [], "chart_type": "heatmap"}

    student_results, _, _ = calculate_proficiency(scores_df, metadata_df)

    # Build heatmap matrix
    matrix = []
    for i, student in enumerate(student_results):
        row_label = f"S{i+1:02d}"  # Further anonymize: S01, S02, etc.
        for std, score in student.scores_by_standard.items():
            matrix.append({
                "student": row_label,
                "standard": std,
                "score": round(score * 100, 1),
            })

    return {"data": matrix, "chart_type": "heatmap"}


@router.get("/story_problem_analysis")
async def story_problem_analysis(
    assessment_id: UUID,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Stacked bar: story problems vs computation performance by DOK level."""
    scores_df, metadata_df = await get_assessment_dataframes(
        assessment_id, current_user.school_id, db
    )
    if scores_df is None:
        return {"data": {}, "chart_type": "stacked_bar"}

    result = analyze_story_vs_computation(scores_df, metadata_df)
    return {"data": result, "chart_type": "stacked_bar"}


@router.get("/progress_over_time")
async def progress_over_time(
    classroom_id: UUID,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Line chart: class proficiency rate over sequential assessments."""
    # Verify classroom belongs to this teacher/school
    classroom = await db.get(Classroom, classroom_id)
    if not classroom or classroom.school_id != current_user.school_id:
        return {"data": [], "chart_type": "line"}

    assessments_result = await db.execute(
        select(Assessment)
        .where(
            Assessment.classroom_id == classroom_id,
            Assessment.school_id == current_user.school_id,
        )
        .order_by(Assessment.week_of.asc())
    )
    assessments = assessments_result.scalars().all()

    time_series = []
    for assessment in assessments:
        scores_df, metadata_df = await get_assessment_dataframes(
            assessment.id, current_user.school_id, db
        )
        if scores_df is None:
            continue
        _, _, summary = calculate_proficiency(scores_df, metadata_df)
        time_series.append({
            "date": assessment.week_of.isoformat() if assessment.week_of else None,
            "assessment_name": assessment.name,
            "proficiency_rate": round(summary.proficiency_rate * 100, 1),
            "assessed_students": summary.assessed_students,
        })

    return {"data": time_series, "chart_type": "line"}


@router.get("/intervention_groups")
async def intervention_groups(
    assessment_id: UUID,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Grouped bar: students by intervention tier."""
    scores_df, metadata_df = await get_assessment_dataframes(
        assessment_id, current_user.school_id, db
    )
    if scores_df is None:
        return {"data": {}, "chart_type": "grouped_bar"}

    student_results, _, _ = calculate_proficiency(scores_df, metadata_df)
    students_list = [{"student_xid": s.student_xid, "pct_score": s.pct_score} for s in student_results]
    groups = build_intervention_groups(students_list)

    return {"data": groups, "chart_type": "grouped_bar"}
