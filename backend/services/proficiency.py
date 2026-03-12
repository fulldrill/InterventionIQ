"""
Proficiency Calculation Engine

Computes proficiency at student, class, and standard levels
from uploaded assessment data. Deterministic — no AI involved.

Proficiency logic:
  student_raw_score = sum(points_earned) / sum(max_points)
  student_is_proficient = student_raw_score >= PROFICIENCY_THRESHOLD (default 0.70)
  class_proficiency_rate = count(proficient_students) / count(assessed_students)
  standard_proficiency = avg score across all questions tagged with that standard
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from core.config import settings


SUPPRESSION_THRESHOLD = settings.small_group_suppression_threshold
PROFICIENCY_THRESHOLD = settings.proficiency_threshold


@dataclass
class StudentResult:
    student_xid: str
    raw_score: float
    max_score: float
    pct_score: float
    is_proficient: bool
    scores_by_standard: Dict[str, float]  # standard_code -> pct_score


@dataclass
class StandardResult:
    standard_code: str
    avg_proficiency: float
    student_count: int
    suppressed: bool  # True if student_count < SUPPRESSION_THRESHOLD


@dataclass
class ClassSummary:
    total_students: int
    assessed_students: int
    proficient_students: int
    proficiency_rate: float
    avg_raw_score: float
    weakest_standards: List[StandardResult]


def parse_score_value(val) -> Optional[float]:
    """
    Parse a score value from CSV. Handles floats, blanks, and edge cases.
    Returns None for absent/missing students.
    """
    if pd.isna(val) or str(val).strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def calculate_proficiency(
    scores_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> Tuple[List[StudentResult], List[StandardResult], ClassSummary]:
    """
    Main proficiency calculation function.

    Args:
        scores_df: DataFrame from assessment CSV.
                   Rows = students. Columns = Q1..QN + student_xid.
        metadata_df: DataFrame from metadata CSV.
                     Columns: question_number, standards, max_points, question_type, dok_level

    Returns:
        Tuple of (student_results, standard_results, class_summary)
    """
    # Build question-to-standard mapping from metadata
    q_to_standard: Dict[int, List[str]] = {}
    q_to_max_points: Dict[int, float] = {}

    for _, row in metadata_df.iterrows():
        q_num = int(row["question_number"])
        standards_raw = str(row.get("standards", "")).strip()
        standards = [s.strip() for s in standards_raw.split(",") if s.strip()]
        q_to_standard[q_num] = standards
        q_to_max_points[q_num] = float(row.get("max_points", 1.0))

    # Identify score columns
    score_cols = {}
    for col in scores_df.columns:
        if col.startswith("Q") and "(") in col:
            try:
                q_num = int(col.split("Q")[1].split(" ")[0])
                score_cols[q_num] = col
            except (ValueError, IndexError):
                continue

    student_results: List[StudentResult] = []
    standard_scores: Dict[str, List[float]] = {}  # standard -> list of pct scores

    for _, row in scores_df.iterrows():
        xid = str(row.get("student_xid", row.get("Student Assignment XID (DO NOT CHANGE)", ""))).strip()
        if not xid:
            continue

        total_earned = 0.0
        total_possible = 0.0
        by_standard: Dict[str, List[float]] = {}
        has_any_score = False

        for q_num, col in score_cols.items():
            max_pts = q_to_max_points.get(q_num, 1.0)
            earned = parse_score_value(row.get(col))

            if earned is None:
                continue  # Skip missing/absent questions

            has_any_score = True
            total_earned += min(earned, max_pts)  # Cap at max points
            total_possible += max_pts

            pct = min(earned, max_pts) / max_pts if max_pts > 0 else 0.0

            for std in q_to_standard.get(q_num, []):
                if std not in by_standard:
                    by_standard[std] = []
                by_standard[std].append(pct)

        if not has_any_score or total_possible == 0:
            continue  # Skip students with no scores (absent / not submitted)

        pct_score = total_earned / total_possible
        is_proficient = pct_score >= PROFICIENCY_THRESHOLD

        # Aggregate by standard for this student
        std_pct: Dict[str, float] = {
            std: float(np.mean(scores)) for std, scores in by_standard.items()
        }

        # Add to class-level standard aggregation
        for std, pct in std_pct.items():
            if std not in standard_scores:
                standard_scores[std] = []
            standard_scores[std].append(pct)

        student_results.append(StudentResult(
            student_xid=xid,
            raw_score=total_earned,
            max_score=total_possible,
            pct_score=pct_score,
            is_proficient=is_proficient,
            scores_by_standard=std_pct,
        ))

    # Build standard results with suppression
    standard_results: List[StandardResult] = []
    for std, scores in standard_scores.items():
        count = len(scores)
        suppressed = count < SUPPRESSION_THRESHOLD
        standard_results.append(StandardResult(
            standard_code=std,
            avg_proficiency=float(np.mean(scores)) if not suppressed else 0.0,
            student_count=count,
            suppressed=suppressed,
        ))

    # Sort by avg_proficiency ascending (weakest first)
    standard_results.sort(key=lambda x: (x.suppressed, x.avg_proficiency))

    # Class summary
    assessed = len(student_results)
    proficient = sum(1 for s in student_results if s.is_proficient)
    avg_raw = float(np.mean([s.pct_score for s in student_results])) if student_results else 0.0

    class_summary = ClassSummary(
        total_students=len(scores_df),
        assessed_students=assessed,
        proficient_students=proficient,
        proficiency_rate=proficient / assessed if assessed > 0 else 0.0,
        avg_raw_score=avg_raw,
        weakest_standards=[s for s in standard_results[:5] if not s.suppressed],
    )

    return student_results, standard_results, class_summary
