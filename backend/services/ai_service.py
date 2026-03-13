"""AI instructional service with anonymized assessment-grounded context."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from statistics import mean
from typing import Any
from uuid import UUID, uuid4

from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import pseudonymize_student
from models.assessment import Assessment, Question, StudentScore
from models.school import Classroom, School
from models.user import User

logger = logging.getLogger(__name__)


def _get_ai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key)

STANDARD_MISSING_MESSAGE = "Insufficient data for {standard_id}"
STANDARD_CODE_PATTERN = re.compile(r"(?:CCSS\.Math\.Content\.)?(\d\.[A-Z]{1,4}\.[A-Z]\.\d+)", re.IGNORECASE)

SYSTEM_PROMPT = """You are the InterventionIQ instructional assistant for Maryland CCSS math.

Grounding and safety constraints:
- Use only the anonymized assessment context provided in this request.
- Do not infer facts that are not present in the provided context.
- If a requested standard is not in context, answer exactly: Insufficient data for [Standard ID]
- Never expose or request student names, IDs, or re-identification.

Instructional output expectations:
- Cite standard IDs in every recommendation.
- Separate recommendations into Tier 1, Tier 2, and Tier 3 support.
- Keep responses concise, actionable, and teacher-friendly.

Chart mode:
When a chart is requested, return only JSON with this schema:
{"chart_spec": {"chart_type": "bar|heatmap|line|scatter|stacked_bar|grouped_bar|distribution", "metric": "proficiency_by_standard|student_vs_standard|progress_over_time|literacy_correlation|story_vs_computation|intervention_groups|score_distribution", "group_by": "class|standard|student|week", "color_metric": "proficiency|score|tier", "title": "Chart title"}}
"""


def _normalize_standard(standard_code: str) -> str:
    code = standard_code.strip()
    if code.upper().startswith("CCSS.MATH.CONTENT."):
        return code.split(".", 3)[-1].upper()
    return code.upper()


def _extract_requested_standards(question: str) -> list[str]:
    found = []
    for match in STANDARD_CODE_PATTERN.findall(question or ""):
        code = _normalize_standard(match)
        if code not in found:
            found.append(code)
    return found


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9\.]+", text.lower()) if len(tok) >= 3}


def _build_rag_chunks(context: dict[str, Any]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []

    class_level = context.get("class_level", {})
    chunks.append(
        {
            "topic": "class_summary",
            "text": (
                f"Assessment {context.get('assessment_name', 'Unknown')}. "
                f"Students assessed: {class_level.get('assessed_students', 0)}. "
                f"Class average: {class_level.get('class_average_pct', 0):.1f}%. "
                f"Class proficiency rate: {class_level.get('class_proficiency_rate_pct', 0):.1f}%."
            ),
        }
    )

    for standard in context.get("standard_level", []):
        chunks.append(
            {
                "topic": "standard",
                "text": (
                    f"Standard {standard['standard_id']} proficiency {standard['proficiency_pct']:.1f}%. "
                    f"Student count {standard['student_count']}. "
                    f"High-Need: {'yes' if standard['is_high_need'] else 'no'}."
                ),
            }
        )

    for item in context.get("item_analysis", []):
        chunks.append(
            {
                "topic": "item_analysis",
                "text": (
                    f"Question type {item['question_type']} average score {item['avg_score_pct']:.1f}%. "
                    f"Items counted {item['item_count']}."
                ),
            }
        )

    return chunks


def _retrieve_rag_chunks(question: str, chunks: list[dict[str, str]], top_k: int) -> list[dict[str, str]]:
    if not chunks:
        return []

    q_tokens = _tokenize(question)
    scored: list[tuple[int, dict[str, str]]] = []

    for chunk in chunks:
        c_tokens = _tokenize(chunk.get("text", ""))
        overlap = len(q_tokens & c_tokens)
        scored.append((overlap, chunk))

    scored.sort(key=lambda row: row[0], reverse=True)
    ranked = [chunk for score, chunk in scored if score > 0]
    if ranked:
        return ranked[:top_k]
    return chunks[: min(2, len(chunks))]


async def build_assessment_ai_context(
    assessment_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any]:
    """Build anonymized analytics context for AI, scoped to school and teacher."""
    assessment = await db.get(Assessment, assessment_id)
    if not assessment or assessment.school_id != current_user.school_id:
        raise ValueError("Assessment not found")

    classroom = None
    if assessment.classroom_id:
        classroom = await db.get(Classroom, assessment.classroom_id)

    if current_user.role == "teacher":
        if not classroom or classroom.teacher_id != current_user.id:
            raise PermissionError("You do not have access to this assessment")

    school = await db.get(School, current_user.school_id)
    school_secret = school.secret_key if school and school.secret_key else settings.secret_key.encode("utf-8")

    rows_result = await db.execute(
        select(StudentScore, Question)
        .join(Question, StudentScore.question_id == Question.id)
        .where(StudentScore.assessment_id == assessment_id)
    )
    rows = rows_result.fetchall()
    if not rows:
        raise ValueError("No assessment data available")

    student_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"earned": 0.0, "possible": 0.0})
    student_standard_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    standard_scores: dict[str, list[float]] = defaultdict(list)
    question_type_scores: dict[str, list[float]] = defaultdict(list)
    question_type_counts: dict[str, set[int]] = defaultdict(set)

    for score, question in rows:
        max_points = float(question.max_points or 1.0)
        safe_max = max(max_points, 1.0)
        earned = max(0.0, min(float(score.points_earned), safe_max))
        pct = earned / safe_max

        student_alias = pseudonymize_student(score.student_xid, school_secret)
        student_totals[student_alias]["earned"] += earned
        student_totals[student_alias]["possible"] += safe_max

        question_type = (question.question_type or "Unknown").strip() or "Unknown"
        question_type_scores[question_type].append(pct)
        question_type_counts[question_type].add(question.question_number)

        for raw_standard in question.standards or []:
            standard_id = raw_standard.strip()
            if not standard_id:
                continue
            student_standard_scores[student_alias][standard_id].append(pct)

    student_level = []
    for student_alias, totals in student_totals.items():
        possible = totals["possible"]
        overall = (totals["earned"] / possible) if possible > 0 else 0.0
        per_standard = {
            standard_id: round(mean(scores) * 100, 1)
            for standard_id, scores in student_standard_scores.get(student_alias, {}).items()
            if scores
        }
        student_level.append(
            {
                "student_key": student_alias,
                "overall_proficiency_pct": round(overall * 100, 1),
                "standard_proficiency_pct": per_standard,
            }
        )

    for student in student_level:
        for standard_id, pct in student["standard_proficiency_pct"].items():
            standard_scores[standard_id].append(pct)

    standard_level = []
    for standard_id, scores in standard_scores.items():
        if not scores:
            continue
        avg_pct = round(mean(scores), 1)
        standard_level.append(
            {
                "standard_id": standard_id,
                "proficiency_pct": avg_pct,
                "student_count": len(scores),
                "is_high_need": avg_pct < (settings.proficiency_threshold * 100),
            }
        )
    standard_level.sort(key=lambda row: row["proficiency_pct"])

    item_analysis = []
    for question_type, scores in question_type_scores.items():
        if not scores:
            continue
        item_analysis.append(
            {
                "question_type": question_type,
                "avg_score_pct": round(mean(scores) * 100, 1),
                "item_count": len(question_type_counts.get(question_type, set())),
            }
        )
    item_analysis.sort(key=lambda row: row["avg_score_pct"])

    assessed_students = len(student_level)
    class_avg = round(mean([s["overall_proficiency_pct"] for s in student_level]), 1) if student_level else 0.0
    proficient_count = sum(
        1 for s in student_level if s["overall_proficiency_pct"] >= (settings.proficiency_threshold * 100)
    )

    context = {
        "assessment_id": str(assessment.id),
        "assessment_name": assessment.name,
        "classroom_id": str(assessment.classroom_id) if assessment.classroom_id else None,
        "classroom_name": classroom.name if classroom else "Unknown",
        "teacher_id": str(current_user.id),
        "school_id": str(current_user.school_id),
        "mapping_session_key": str(uuid4()),
        "class_level": {
            "assessed_students": assessed_students,
            "class_average_pct": class_avg,
            "class_proficiency_rate_pct": round((proficient_count / assessed_students) * 100, 1)
            if assessed_students > 0
            else 0.0,
            "proficiency_threshold_pct": round(settings.proficiency_threshold * 100, 1),
        },
        "student_level": student_level,
        "standard_level": standard_level,
        "high_need_standards": [row["standard_id"] for row in standard_level if row["is_high_need"]],
        "item_analysis": item_analysis,
    }
    context["rag_chunks"] = _build_rag_chunks(context)
    return context


def _build_prompt_context(assessment_context: dict[str, Any], chunks: list[dict[str, str]]) -> str:
    context_lines = [
        "=== ANONYMIZED ASSESSMENT CONTEXT ===",
        json.dumps(
            {
                "assessment_name": assessment_context.get("assessment_name"),
                "class_level": assessment_context.get("class_level", {}),
                "standard_level": assessment_context.get("standard_level", []),
                "high_need_standards": assessment_context.get("high_need_standards", []),
                "item_analysis": assessment_context.get("item_analysis", []),
            },
            ensure_ascii=True,
        ),
        "",
        "=== RETRIEVED CONTEXT CHUNKS ===",
    ]
    for idx, chunk in enumerate(chunks, start=1):
        context_lines.append(f"[{idx}] {chunk.get('text', '')}")
    return "\n".join(context_lines)


async def chat_with_ai(
    question: str,
    assessment_context: dict[str, Any],
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Ask OpenAI with strict assessment-grounded, anonymized context."""
    available = {_normalize_standard(s["standard_id"]) for s in assessment_context.get("standard_level", [])}
    requested = _extract_requested_standards(question)
    missing = [std for std in requested if std not in available]
    if missing:
        return {
            "response": "\n".join(STANDARD_MISSING_MESSAGE.format(standard_id=std) for std in missing),
            "chart_spec": None,
        }

    rag_chunks = assessment_context.get("rag_chunks", [])
    retrieved = _retrieve_rag_chunks(question, rag_chunks, settings.rag_top_k)
    context_block = _build_prompt_context(assessment_context, retrieved)

    messages: list[dict[str, str]] = []
    for msg in conversation_history or []:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content.strip():
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": f"{context_block}\n\nTeacher question: {question}"})

    try:
        client = _get_ai_client()
        completion = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=settings.ai_max_tokens,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages,
            ],
        )
        response_text = (completion.choices[0].message.content or "").strip() if completion.choices else ""
        if response_text.startswith("{") and "chart_spec" in response_text:
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict) and "chart_spec" in parsed:
                    return {"response": None, "chart_spec": parsed["chart_spec"]}
            except json.JSONDecodeError:
                logger.warning("OpenAI returned malformed chart JSON")

        return {"response": response_text, "chart_spec": None}
    except RuntimeError as exc:
        logger.error("AI configuration error: %s", exc)
        return {"response": "OPENAI_API_KEY is missing in backend .env.", "chart_spec": None}
    except OpenAIError as exc:
        logger.error("OpenAI API error: %s", exc)
        return {"response": "AI provider error. Please try again shortly.", "chart_spec": None}
    except Exception as exc:
        logger.error("AI service failure: %s", exc)
        return {"response": "Unable to generate a response right now.", "chart_spec": None}
