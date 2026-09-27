"""Closed portable playlist references. No environment, credentials, or local paths."""

from __future__ import annotations

import json
import re
from typing import Any

from changgeun.domain.models import DomainError, normalized_name


def validate_references(references: Any) -> list[dict[str, Any]]:
    if not isinstance(references, list) or len(references) > 500:
        raise DomainError("invalid_import_references")
    for reference in references:
        if (
            not isinstance(reference, dict)
            or set(reference) - {"source_type", "external_id", "title", "annotations"}
            or not {"source_type", "external_id", "title"} <= reference.keys()
        ):
            raise DomainError("invalid_import_references")
        source, identifier, title = (
            reference[key] for key in ("source_type", "external_id", "title")
        )
        if (
            source not in {"youtube", "approved_audio"}
            or not isinstance(identifier, str)
            or not isinstance(title, str)
            or not title
            or len(title) > 500
        ):
            raise DomainError("invalid_import_references")
        pattern = r"[A-Za-z0-9_-]{11}" if source == "youtube" else r"[A-Za-z0-9_-]{1,100}"
        if not re.fullmatch(pattern, identifier):
            raise DomainError("invalid_import_references")
        annotations = reference.get("annotations", {})
        if not isinstance(annotations, dict) or set(annotations) - {"aliases", "tags", "creator"}:
            raise DomainError("invalid_import_references")
        for key in ("aliases", "tags"):
            values = annotations.get(key, [])
            if not isinstance(values, list) or len(values) > 20:
                raise DomainError("invalid_import_references")
            for value in values:
                if not isinstance(value, str):
                    raise DomainError("invalid_import_references")
                normalized_name(value)
        if "creator" in annotations:
            if not isinstance(annotations["creator"], str):
                raise DomainError("invalid_import_references")
            normalized_name(annotations["creator"])
    return references


def parse_export(data: bytes) -> list[dict[str, Any]]:
    if len(data) > 524288:
        raise DomainError("import_file_too_large")
    try:
        raw = json.loads(data)
    except (ValueError, UnicodeError):
        raise DomainError("invalid_import_file") from None
    if (
        not isinstance(raw, dict)
        or set(raw) != {"schema_version", "tracks"}
        or type(raw["schema_version"]) is not int
        or raw["schema_version"] != 1
    ):
        raise DomainError("invalid_import_file")
    return validate_references(raw["tracks"])
