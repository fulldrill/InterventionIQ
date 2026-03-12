"""
AI Instructional Assistant Service

RAG pipeline: retrieve relevant knowledge chunks from pgvector,
assemble prompt with anonymized student data context,
call Claude API, parse response (text or chart_spec).

PRIVACY GUARANTEE: No student names or real IDs are ever sent to Claude.
"""
import json
import logging
from typing import Optional
from uuid import UUID

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import pseudonymize_student

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are an instructional analysis assistant for a K-8 school using Maryland Common Core Standards.

You have access to:
- Maryland Common Core Math Standards (grades 3-8)
- Reveal Math teacher manuals and unit guides
- School intervention guidance documents

IMPORTANT RULES:
1. All student data provided to you has been anonymized. Student identifiers like "Student-A7F2" are pseudonyms only.
2. Never attempt to identify or speculate about individual students' real identities.
3. Cite specific CCSS standard codes (e.g., 3.OA.C.7, 3.NF.A.1) in every recommendation.
4. When recommending interventions, be specific about the instructional strategy and standard cluster.
5. Keep responses concise and teacher-facing. Avoid academic jargon.
6. Never use em dashes in responses. Use regular hyphens.

CHART GENERATION:
When a teacher requests a visualization, respond ONLY with a JSON object in this exact format:
{"chart_spec": {"chart_type": "bar|heatmap|line|scatter|stacked_bar|grouped_bar|distribution", "metric": "proficiency_by_standard|student_vs_standard|progress_over_time|literacy_correlation|story_vs_computation|intervention_groups|score_distribution", "group_by": "class|standard|student|week", "color_metric": "proficiency|score|tier", "title": "Chart title"}}

Do not mix text responses with chart_spec. Return one or the other.

Current date context will be provided with each request."""


async def retrieve_knowledge_chunks(
    query: str,
    db: AsyncSession,
    school_id: Optional[UUID] = None,
    top_k: int = None,
) -> list[dict]:
    """
    Retrieve relevant knowledge chunks from pgvector using cosine similarity.
    NOTE: Embedding generation is TODO - integrate embedding model here.
    """
    if top_k is None:
        top_k = settings.rag_top_k

    # TODO: Generate query embedding using embedding model
    # For MVP scaffold: return empty list and rely on system prompt only
    # In production: embed query, then run pgvector similarity search
    logger.warning("RAG retrieval not yet implemented - returning empty context")
    return []

    # Production implementation would be:
    # query_embedding = await generate_embedding(query)
    # result = await db.execute(text("""
    #     SELECT content, document_name, standard_code, document_type,
    #            1 - (embedding <=> :embedding) as similarity
    #     FROM knowledge_chunks
    #     WHERE (school_id = :school_id OR school_id IS NULL)
    #     ORDER BY embedding <=> :embedding
    #     LIMIT :top_k
    # """), {"embedding": str(query_embedding), "school_id": str(school_id), "top_k": top_k})
    # return [dict(row) for row in result.fetchall()]


def build_context_from_data(
    anonymized_stats: dict,
    knowledge_chunks: list[dict],
) -> str:
    """
    Assemble the context block for the Claude prompt.
    anonymized_stats must contain ONLY aggregated/anonymized data.
    """
    context_parts = []

    if anonymized_stats:
        context_parts.append("=== CURRENT CLASS DATA (ANONYMIZED) ===")
        if "class_proficiency_rate" in anonymized_stats:
            pct = anonymized_stats["class_proficiency_rate"] * 100
            context_parts.append(f"Class proficiency rate: {pct:.1f}%")
        if "assessed_students" in anonymized_stats:
            context_parts.append(f"Students assessed: {anonymized_stats['assessed_students']}")
        if "weakest_standards" in anonymized_stats:
            context_parts.append("Weakest standards (ascending proficiency):")
            for std in anonymized_stats["weakest_standards"][:5]:
                pct = std.get("avg_proficiency", 0) * 100
                context_parts.append(f"  - {std['standard_code']}: {pct:.1f}%")
        context_parts.append("")

    if knowledge_chunks:
        context_parts.append("=== RELEVANT KNOWLEDGE BASE EXCERPTS ===")
        for i, chunk in enumerate(knowledge_chunks, 1):
            context_parts.append(f"[Source {i}: {chunk.get('document_name', 'Unknown')}]")
            context_parts.append(chunk.get("content", ""))
            context_parts.append("")

    return "\n".join(context_parts)


async def chat_with_ai(
    question: str,
    anonymized_stats: dict,
    db: AsyncSession,
    school_id: UUID,
    conversation_history: list[dict] = None,
) -> dict:
    """
    Main AI chat function. Returns {"response": str} or {"chart_spec": dict}.

    PRIVACY: anonymized_stats must not contain real student names or IDs.
    """
    try:
        # Retrieve relevant knowledge chunks
        knowledge_chunks = await retrieve_knowledge_chunks(question, db, school_id)

        # Build context
        context = build_context_from_data(anonymized_stats, knowledge_chunks)

        # Build message list
        messages = conversation_history or []
        user_message = f"{context}\n\n=== TEACHER QUESTION ===\n{question}"
        messages = messages + [{"role": "user", "content": user_message}]

        # Call Claude API
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.ai_max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        raw_text = response.content[0].text.strip()

        # Check if response is a chart spec
        if raw_text.startswith("{") and "chart_spec" in raw_text:
            try:
                parsed = json.loads(raw_text)
                if "chart_spec" in parsed:
                    return {"chart_spec": parsed["chart_spec"], "response": None}
            except json.JSONDecodeError:
                pass  # Fall through to text response

        return {"response": raw_text, "chart_spec": None}

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return {
            "response": "I am unable to process your request right now. Please try again shortly.",
            "chart_spec": None,
        }
    except Exception as e:
        logger.error(f"AI service error: {e}")
        return {
            "response": "An error occurred while processing your question.",
            "chart_spec": None,
        }
