from __future__ import annotations

from pathlib import Path


def build_run_id(project_name: str) -> str:
    cleaned = project_name.strip().replace(" ", "-")
    return f"{cleaned}_run_001"


def run_detection_agent(file_name: str, company_id: str = "001") -> dict:
    """
    Detection Agent v1.

    Current version is a deterministic mock for RA-N01.
    Later this function will call a vision/model pipeline and return the same schema.
    """

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
                "confidence": 93,
                "evidence_pages": "1,2,3",
                "detected_materials": "Formica Birman 2650; stainless steel; oak veneer",
                "dimensions_json": {
                    "width_mm": 5095,
                    "depth_mm": 700,
                    "height_mm": 2946,
                },
                "notes": "Main kitchen with cabinetry, stainless elements, countertop and backsplash.",
                "approved": False,
                "created_at": "18.06.2026",
            },
            {
                "run_id": run_id,
                "company_id": company_id,
                "object_id": "02_kitchen_island",
                "object_name": "Kitchen island",
                "quantity": 1,
                "confidence": 89,
                "evidence_pages": "1,2",
                "detected_materials": "Formica; stainless steel; Marble Laba Rosa stone",
                "dimensions_json": {
                    "width_mm": 4495,
                    "depth_mm": 1100,
                    "height_mm": 1000,
                },
                "notes": "Island with stone/stainless countertop and cabinetry elements.",
                "approved": False,
                "created_at": "18.06.2026",
            },
            {
                "run_id": run_id,
                "company_id": company_id,
                "object_id": "03_wall_shelf",
                "object_name": "Wall shelf",
                "quantity": 1,
                "confidence": 95,
                "evidence_pages": "1,3,7",
                "detected_materials": "Oak veneer; corten steel; LED profile",
                "dimensions_json": {
                    "width_mm": 4495,
                    "depth_mm": 300,
                    "height_mm": 700,
                },
                "notes": "Wall shelf with partitions, hidden mounting and integrated LED.",
                "approved": False,
                "created_at": "18.06.2026",
            },
        ],
    }
