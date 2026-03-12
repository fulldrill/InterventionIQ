"""
CSV Ingestion Service

Validates and parses uploaded assessment CSVs.
Handles Reveal Math format and normalized custom format.
"""
import io
import re
import pandas as pd
from typing import Tuple, List, Optional
from fastapi import HTTPException, status

from core.config import settings

MAX_ROWS = settings.max_csv_upload_rows
MAX_FILE_SIZE_MB = settings.max_csv_file_size_mb

# Expected metadata columns
METADATA_REQUIRED_COLS = {"question_number", "question_type", "max_points", "standards", "dok_level"}

# Reveal Math XID column name
REVEAL_XID_COL = "Student Assignment XID (DO NOT CHANGE)"


def validate_file_size(content: bytes) -> None:
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB"
        )


def parse_reveal_assessment_csv(content: bytes) -> Tuple[pd.DataFrame, List[str]]:
    """
    Parse Reveal Math assessment CSV.
    Expected format:
    - Header row: Q1 (1 point), Q2 (1 point), ..., Student Assignment XID (DO NOT CHANGE)
    - Data rows: numeric scores, student URN

    Returns: (dataframe with normalized columns, list of validation warnings)
    """
    validate_file_size(content)
    warnings = []

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse CSV file: {str(e)}"
        )

    if len(df) > MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File contains {len(df)} rows. Maximum allowed: {MAX_ROWS}"
        )

    # Find student ID column (Reveal format or custom 'student_xid')
    xid_col = None
    if REVEAL_XID_COL in df.columns:
        xid_col = REVEAL_XID_COL
    elif "student_xid" in df.columns:
        xid_col = "student_xid"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing student identifier column. Expected '{REVEAL_XID_COL}' or 'student_xid'"
        )

    # Find question score columns: "Q{N} ({P} point(s))" or "Q{N}"
    score_cols = {}
    for col in df.columns:
        match = re.match(r"Q(\d+)\s*\(", col)
        if match:
            q_num = int(match.group(1))
            score_cols[q_num] = col

    if not score_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No question score columns found. Expected format: 'Q1 (1 point)', 'Q2 (1 point)', etc."
        )

    # Validate score values are numeric or blank
    for q_num, col in score_cols.items():
        non_numeric = df[col].dropna().apply(
            lambda x: pd.to_numeric(x, errors='coerce')
        ).isna().sum()
        if non_numeric > 0:
            warnings.append(f"Column '{col}' contains {non_numeric} non-numeric values — these will be treated as missing")

    # Rename XID column to normalized name
    df = df.rename(columns={xid_col: "student_xid"})

    # Drop rows with no student XID
    before = len(df)
    df = df.dropna(subset=["student_xid"])
    if len(df) < before:
        warnings.append(f"Dropped {before - len(df)} rows with missing student identifiers")

    return df, warnings


def parse_metadata_csv(content: bytes) -> Tuple[pd.DataFrame, List[str]]:
    """
    Parse question metadata CSV (Reveal Math MetaData format).
    Normalizes column names and validates required fields.
    """
    validate_file_size(content)
    warnings = []

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse metadata CSV: {str(e)}"
        )

    # Normalize column names (lowercase, strip, replace spaces with underscores)
    df.columns = [c.strip().lower().replace(" ", "_").replace("(s)", "s") for c in df.columns]

    # Handle Reveal Math column names
    col_mapping = {
        "question": "question_number",
        "type": "question_type",
        "points": "max_points",
        "standardss": "standards",  # After the (s) replacement
        "dok": "dok_level",
    }
    df = df.rename(columns=col_mapping)

    # Validate required columns
    missing = METADATA_REQUIRED_COLS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Metadata CSV missing required columns: {', '.join(missing)}"
        )

    # Validate question numbers are integers
    df["question_number"] = pd.to_numeric(df["question_number"], errors="coerce")
    null_q = df["question_number"].isna().sum()
    if null_q > 0:
        warnings.append(f"{null_q} rows have invalid question numbers and will be skipped")
        df = df.dropna(subset=["question_number"])

    df["question_number"] = df["question_number"].astype(int)
    df["max_points"] = pd.to_numeric(df["max_points"], errors="coerce").fillna(1.0)

    return df, warnings


def parse_literacy_csv(content: bytes) -> Tuple[pd.DataFrame, List[str]]:
    """
    Parse literacy assessment CSV.
    Required columns: student_xid, total_score
    Optional: reading_comprehension, fluency_wpm, accuracy_pct, assessment_date
    """
    validate_file_size(content)
    warnings = []

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse literacy CSV: {str(e)}"
        )

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = {"student_xid", "total_score"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Literacy CSV missing required columns: {', '.join(missing)}"
        )

    df["total_score"] = pd.to_numeric(df["total_score"], errors="coerce")
    invalid = df["total_score"].isna().sum()
    if invalid > 0:
        warnings.append(f"{invalid} rows have invalid total_score and will be skipped")
        df = df.dropna(subset=["total_score"])

    # Normalize score to 0-1 range if > 1 (assumes percentage out of 100)
    if df["total_score"].max() > 1.5:
        df["total_score_pct"] = df["total_score"] / 100.0
    else:
        df["total_score_pct"] = df["total_score"]

    return df, warnings
