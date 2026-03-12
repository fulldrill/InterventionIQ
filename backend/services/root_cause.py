"""
Root Cause Analysis Engine

Identifies WHY students are struggling by analyzing:
- Story problems vs computation performance (DOK + question type)
- Standard cluster weakness (grouped by CCSS domain)
- Literacy vs math correlation
- Intervention tier assignment
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from enum import Enum
from scipy.stats import pearsonr

from core.config import settings

SUPPRESSION_THRESHOLD = settings.small_group_suppression_threshold


class InterventionTier(str, Enum):
    TIER_1 = "Tier 1 - Enrichment"          # >= 85% proficiency
    TIER_2 = "Tier 2 - Strategic"             # 60% - 84%
    TIER_3 = "Tier 3 - Intensive"             # < 60%


# Question types treated as "story problems / word problems"
STORY_PROBLEM_TYPES = {
    "Multiple Choice",
    "Multiple Choice, Multiple Select",
    "Essay",
}

# Question types treated as "computation"
COMPUTATION_TYPES = {
    "Fill In The Blank",
    "Matching",
}


def assign_intervention_tier(pct_score: float) -> InterventionTier:
    if pct_score >= 0.85:
        return InterventionTier.TIER_1
    elif pct_score >= 0.60:
        return InterventionTier.TIER_2
    else:
        return InterventionTier.TIER_3


def analyze_story_vs_computation(
    scores_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> Dict:
    """
    Compare class performance on story problems vs computation questions.
    Returns breakdown by question type and DOK level.
    """
    results = {
        "story_problem_avg": None,
        "computation_avg": None,
        "by_dok": {},
        "suppressed": False,
    }

    story_scores = []
    comp_scores = []
    dok_scores: Dict[str, List[float]] = {}

    # Build metadata lookup
    q_meta: Dict[int, dict] = {}
    for _, row in metadata_df.iterrows():
        q_num = int(row["question_number"])
        q_meta[q_num] = {
            "type": str(row.get("question_type", "")),
            "dok": str(row.get("dok_level", "")),
            "max_points": float(row.get("max_points", 1.0)),
        }

    for _, row in scores_df.iterrows():
        for col in scores_df.columns:
            if not (col.startswith("Q") and "(" in col):
                continue
            try:
                q_num = int(col.split("Q")[1].split(" ")[0])
            except (ValueError, IndexError):
                continue

            meta = q_meta.get(q_num)
            if not meta:
                continue

            val = row.get(col)
            if pd.isna(val) or str(val).strip() == "":
                continue

            earned = min(float(val), meta["max_points"])
            pct = earned / meta["max_points"] if meta["max_points"] > 0 else 0.0

            q_type = meta["type"]
            dok = meta["dok"]

            if q_type in STORY_PROBLEM_TYPES:
                story_scores.append(pct)
            elif q_type in COMPUTATION_TYPES:
                comp_scores.append(pct)

            if dok:
                if dok not in dok_scores:
                    dok_scores[dok] = []
                dok_scores[dok].append(pct)

    n_students = len(scores_df)
    if n_students < SUPPRESSION_THRESHOLD:
        results["suppressed"] = True
        return results

    if story_scores:
        results["story_problem_avg"] = float(np.mean(story_scores))
    if comp_scores:
        results["computation_avg"] = float(np.mean(comp_scores))

    for dok, scores in dok_scores.items():
        results["by_dok"][dok] = float(np.mean(scores))

    return results


def calculate_literacy_correlation(
    math_scores: List[Tuple[str, float]],   # [(student_xid, math_pct), ...]
    literacy_scores: List[Tuple[str, float]], # [(student_xid, literacy_pct), ...]
) -> Dict:
    """
    Pearson correlation between math and literacy scores.
    Requires matching student XIDs.
    Returns correlation coefficient, p-value, and scatter data.
    """
    # Build lookup
    math_map = {xid: score for xid, score in math_scores}
    lit_map = {xid: score for xid, score in literacy_scores}

    # Only include students with BOTH math and literacy scores
    common_xids = set(math_map.keys()) & set(lit_map.keys())

    if len(common_xids) < SUPPRESSION_THRESHOLD:
        return {"suppressed": True, "correlation": None, "p_value": None, "scatter_data": []}

    m_vals = [math_map[xid] for xid in common_xids]
    l_vals = [lit_map[xid] for xid in common_xids]

    corr, p_val = pearsonr(m_vals, l_vals)

    # Build anonymized scatter data (DO NOT include real XIDs)
    scatter = [
        {"math_score": round(m, 3), "literacy_score": round(l, 3)}
        for m, l in zip(m_vals, l_vals)
    ]

    return {
        "suppressed": False,
        "correlation": round(float(corr), 4),
        "p_value": round(float(p_val), 4),
        "student_count": len(common_xids),
        "scatter_data": scatter,
    }


def build_intervention_groups(
    student_results: List[dict],  # [{"student_xid": ..., "pct_score": ...}, ...]
) -> Dict:
    """
    Assign students to intervention tiers.
    Returns tier breakdown with counts and anonymized cohort lists.
    """
    tiers: Dict[str, List[str]] = {
        InterventionTier.TIER_1: [],
        InterventionTier.TIER_2: [],
        InterventionTier.TIER_3: [],
    }

    for student in student_results:
        tier = assign_intervention_tier(student["pct_score"])
        tiers[tier].append(student["student_xid"])

    result = {}
    for tier, xids in tiers.items():
        count = len(xids)
        result[tier] = {
            "count": count,
            "avg_score": None,
            "suppressed": count < SUPPRESSION_THRESHOLD,
        }

        if count >= SUPPRESSION_THRESHOLD:
            matching = [s for s in student_results if s["student_xid"] in xids]
            result[tier]["avg_score"] = float(np.mean([s["pct_score"] for s in matching]))

    return result
