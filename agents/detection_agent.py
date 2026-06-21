from __future__ import annotations

from pathlib import Path

from agents.anthropic_adapter import run_anthropic_detection_agent_with_fallback
from agents.prompt_loader import load_detection_agent_prompt
from agents.schemas.detection_schema import validate_detection_result


def get_secret(name: str, default: str | None = None) -> str | None:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass

    return default


def build_run_id(project_name: str) -> str:
    cleaned = project_name.strip().replace(" ", "-")
    return f"{cleaned}_run_001"


def build_mock_detection_result(file_name: str, company_id: str = "001") -> dict:
    project_name = "RA-N01"
    run_id = build_run_id(project_name)

    return {
        "rfq_run": {
            "run_id": run_id,
            "company_id": company_id,
            "project_name": project_name,
            "file_name": Path(file_name).name,
            "source_type": "pdf_drawing_package",
            "client_or_design_partner": "8DOR",
            "author": "Abdallah",
            "document_date": "16/02/2026",
            "pages_detected": 12,
            "language": "he,en",
            "file_quality_level": 3,
            "file_quality_label": "detailed_drawings",
            "file_quality_confidence": 87,
            "file_quality_notes": (
                "The file includes object names, dimensions, materials and drawing pages. "
                "Some internal construction details and hardware quantities are still unclear."
            ),
            "missing_information": (
                "Exact hardware quantities; some internal cabinet details; final supplier specs."
            ),
            "status": "intake_parsed",
            "created_at": "18.06.2026",
        },
        "detected_objects": [
            {
                "run_id": run_id,
                "company_id": company_id,
                "object_id": "01_kitchen",
                "object_name": "Kitchen",
                "quantity": 1,
                "quantity_explicit": False,
                "quantity_confidence": 80,
                "confidence": 93,
                "evidence_pages": "1,2,3",
                "detected_materials": "Formica Birman 2650; stainless steel; oak veneer",
                "dimensions_json": {
                    "unit": "mm",
                    "width": 5095,
                    "depth": 700,
                    "height": 2946,
                    "thickness": 0,
                    "diameter": 0,
                    "profile_size": "unknown",
                    "raw_text": "5095 × 700 × 2946",
                },
                "notes": (
                    "Main kitchen with cabinetry, stainless elements, countertop and backsplash. "
                    "Quantity is inferred as one built-in kitchen object."
                ),
                "approved": False,
                "created_at": "18.06.2026",
            },
            {
                "run_id": run_id,
                "company_id": company_id,
                "object_id": "02_kitchen_island",
                "object_name": "Kitchen island",
                "quantity": 1,
                "quantity_explicit": False,
                "quantity_confidence": 80,
                "confidence": 89,
                "evidence_pages": "1,2",
                "detected_materials": "Formica; stainless steel; Marble Laba Rosa stone",
                "dimensions_json": {
                    "unit": "mm",
                    "width": 4495,
                    "depth": 1100,
                    "height": 1000,
                    "thickness": 0,
                    "diameter": 0,
                    "profile_size": "unknown",
                    "raw_text": "4495 × 1100 × 1000",
                },
                "notes": (
                    "Island with stone/stainless countertop and cabinetry elements. "
                    "Quantity is inferred as one built-in island object."
                ),
                "approved": False,
                "created_at": "18.06.2026",
            },
            {
                "run_id": run_id,
                "company_id": company_id,
                "object_id": "03_wall_shelf",
                "object_name": "Wall shelf",
                "quantity": 1,
                "quantity_explicit": False,
                "quantity_confidence": 75,
                "confidence": 95,
                "evidence_pages": "1,3,7",
                "detected_materials": "Oak veneer; corten steel; LED profile",
                "dimensions_json": {
                    "unit": "mm",
                    "width": 4495,
                    "depth": 300,
                    "height": 700,
                    "thickness": 0,
                    "diameter": 0,
                    "profile_size": "unknown",
                    "raw_text": "4495 × 300 × 700",
                },
                "notes": (
                    "Wall shelf with partitions, hidden mounting and integrated LED. "
                    "Quantity is inferred from a unique wall shelf scope item."
                ),
                "approved": False,
                "created_at": "18.06.2026",
            },
        ],
    }


def run_detection_agent(
    file_name: str,
    company_id: str = "001",
    file_bytes: bytes | None = None,
) -> dict:
    """
    Detection Agent entrypoint.

    Modes:
    - mock: deterministic local mock, no API cost
    - anthropic: real Claude API call, requires file_bytes
    """

    # Fail loudly if the prompt file is missing or empty.
    _prompt = load_detection_agent_prompt()

    mode = get_secret("DETECTION_AGENT_MODE", "mock") or "mock"
    mode = mode.strip().lower()

    if mode == "mock":
        result = build_mock_detection_result(
            file_name=file_name,
            company_id=company_id,
        )
        return validate_detection_result(result)

    if mode == "anthropic":
        if file_bytes is None:
            raise ValueError(
                "DETECTION_AGENT_MODE='anthropic' requires file_bytes. "
                "Pass uploaded_file.getvalue() from Streamlit."
            )

        return run_anthropic_detection_agent_with_fallback(
            file_name=file_name,
            company_id=company_id,
            file_bytes=file_bytes,
        )

    raise ValueError(
        f"Unknown DETECTION_AGENT_MODE={mode!r}. "
        "Expected 'mock' or 'anthropic'."
    )
