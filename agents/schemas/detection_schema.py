from __future__ import annotations

from typing import Any


STATUS_VALUES = {"intake_parsed", "intake_failed", "unreadable"}

REQUIRED_RUN_FIELDS = {
    "run_id",
    "company_id",
    "project_name",
    "file_name",
    "source_type",
    "client_or_design_partner",
    "author",
    "document_date",
    "pages_detected",
    "language",
    "file_quality_level",
    "file_quality_label",
    "file_quality_confidence",
    "file_quality_notes",
    "missing_information",
    "status",
    "created_at",
}

REQUIRED_OBJECT_FIELDS = {
    "run_id",
    "company_id",
    "object_id",
    "object_name",
    "quantity",
    "quantity_explicit",
    "quantity_confidence",
    "confidence",
    "evidence_pages",
    "detected_materials",
    "dimensions_json",
    "notes",
    "approved",
    "created_at",
}

REQUIRED_DIMENSION_FIELDS = {
    "unit",
    "width",
    "depth",
    "height",
    "thickness",
    "diameter",
    "profile_size",
    "raw_text",
}


DETECTION_RESULT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rfq_run", "detected_objects"],
    "properties": {
        "rfq_run": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(REQUIRED_RUN_FIELDS),
            "properties": {
                "run_id": {"type": "string"},
                "company_id": {"type": "string"},
                "project_name": {"type": "string"},
                "file_name": {"type": "string"},
                "source_type": {"type": "string"},
                "client_or_design_partner": {"type": "string"},
                "author": {"type": "string"},
                "document_date": {"type": "string"},
                "pages_detected": {"type": "integer", "minimum": 0},
                "language": {"type": "string"},
                "file_quality_level": {"type": "integer", "minimum": 0, "maximum": 4},
                "file_quality_label": {"type": "string"},
                "file_quality_confidence": {"type": "number", "minimum": 0, "maximum": 100},
                "file_quality_notes": {"type": "string"},
                "missing_information": {"type": "string"},
                "status": {"type": "string", "enum": sorted(STATUS_VALUES)},
                "created_at": {"type": "string"},
            },
        },
        "detected_objects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(REQUIRED_OBJECT_FIELDS),
                "properties": {
                    "run_id": {"type": "string"},
                    "company_id": {"type": "string"},
                    "object_id": {"type": "string"},
                    "object_name": {"type": "string"},
                    "quantity": {"type": "number", "minimum": 0},
                    "quantity_explicit": {"type": "boolean"},
                    "quantity_confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "evidence_pages": {"type": "string"},
                    "detected_materials": {"type": "string"},
                    "dimensions_json": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": sorted(REQUIRED_DIMENSION_FIELDS),
                        "properties": {
                            "unit": {"type": "string"},
                            "width": {"type": "number"},
                            "depth": {"type": "number"},
                            "height": {"type": "number"},
                            "thickness": {"type": "number"},
                            "diameter": {"type": "number"},
                            "profile_size": {"type": "string"},
                            "raw_text": {"type": "string"},
                        },
                    },
                    "notes": {"type": "string"},
                    "approved": {"type": "boolean"},
                    "created_at": {"type": "string"},
                },
            },
        },
    },
}


class DetectionSchemaError(ValueError):
    pass


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DetectionSchemaError(f"{name} must be dict")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise DetectionSchemaError(f"{name} must be list")
    return value


def _check_required_keys(payload: dict[str, Any], required: set[str], name: str) -> None:
    missing = required - set(payload.keys())
    if missing:
        raise DetectionSchemaError(f"{name} missing keys: {sorted(missing)}")


def _check_no_extra_keys(payload: dict[str, Any], allowed: set[str], name: str) -> None:
    extra = set(payload.keys()) - allowed
    if extra:
        raise DetectionSchemaError(f"{name} has extra keys: {sorted(extra)}")


def _check_number_range(value: Any, name: str, min_value: float, max_value: float) -> None:
    if not isinstance(value, (int, float)):
        raise DetectionSchemaError(f"{name} must be number")
    if value < min_value or value > max_value:
        raise DetectionSchemaError(f"{name} must be between {min_value} and {max_value}")


def validate_detection_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Validates Detection Agent output before Supabase write.

    This intentionally uses plain Python instead of Pydantic so the app does not
    need a new dependency yet.
    """
    result = _require_dict(result, "detection_result")
    _check_required_keys(result, {"rfq_run", "detected_objects"}, "detection_result")
    _check_no_extra_keys(result, {"rfq_run", "detected_objects"}, "detection_result")

    rfq_run = _require_dict(result["rfq_run"], "rfq_run")
    detected_objects = _require_list(result["detected_objects"], "detected_objects")

    _check_required_keys(rfq_run, REQUIRED_RUN_FIELDS, "rfq_run")
    _check_no_extra_keys(rfq_run, REQUIRED_RUN_FIELDS, "rfq_run")

    if rfq_run["status"] not in STATUS_VALUES:
        raise DetectionSchemaError(
            f"rfq_run.status must be one of {sorted(STATUS_VALUES)}"
        )

    if not isinstance(rfq_run["pages_detected"], int):
        raise DetectionSchemaError("rfq_run.pages_detected must be integer")

    if not isinstance(rfq_run["file_quality_level"], int):
        raise DetectionSchemaError("rfq_run.file_quality_level must be integer")

    if rfq_run["file_quality_level"] < 0 or rfq_run["file_quality_level"] > 4:
        raise DetectionSchemaError("rfq_run.file_quality_level must be between 0 and 4")

    _check_number_range(
        rfq_run["file_quality_confidence"],
        "rfq_run.file_quality_confidence",
        0,
        100,
    )

    if rfq_run["status"] in {"unreadable", "intake_failed"} and detected_objects:
        raise DetectionSchemaError(
            "detected_objects must be [] when status is unreadable or intake_failed"
        )

    for index, obj in enumerate(detected_objects):
        obj_name = f"detected_objects[{index}]"
        obj = _require_dict(obj, obj_name)

        _check_required_keys(obj, REQUIRED_OBJECT_FIELDS, obj_name)
        _check_no_extra_keys(obj, REQUIRED_OBJECT_FIELDS, obj_name)

        if obj["run_id"] != rfq_run["run_id"]:
            raise DetectionSchemaError(f"{obj_name}.run_id must match rfq_run.run_id")

        if obj["company_id"] != rfq_run["company_id"]:
            raise DetectionSchemaError(
                f"{obj_name}.company_id must match rfq_run.company_id"
            )

        _check_number_range(obj["quantity"], f"{obj_name}.quantity", 0, 999999)
        _check_number_range(
            obj["quantity_confidence"],
            f"{obj_name}.quantity_confidence",
            0,
            100,
        )
        _check_number_range(obj["confidence"], f"{obj_name}.confidence", 0, 100)

        if not isinstance(obj["quantity_explicit"], bool):
            raise DetectionSchemaError(f"{obj_name}.quantity_explicit must be boolean")

        if not isinstance(obj["approved"], bool):
            raise DetectionSchemaError(f"{obj_name}.approved must be boolean")

        dimensions = _require_dict(obj["dimensions_json"], f"{obj_name}.dimensions_json")
        _check_required_keys(
            dimensions,
            REQUIRED_DIMENSION_FIELDS,
            f"{obj_name}.dimensions_json",
        )
        _check_no_extra_keys(
            dimensions,
            REQUIRED_DIMENSION_FIELDS,
            f"{obj_name}.dimensions_json",
        )

        for key in ["width", "depth", "height", "thickness", "diameter"]:
            _check_number_range(
                dimensions[key],
                f"{obj_name}.dimensions_json.{key}",
                0,
                999999,
            )

    return result
