"""
Metric Protocol Auditor - JSON Schema Definitions

This module provides JSON schema definitions for validating metric data structures.
"""
from __future__ import annotations

import json
from pathlib import Path

# Schema for MetricDefinition
METRIC_DEFINITION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["metric_id", "canonical_name", "task_type", "direction", "formula"],
    "properties": {
        "metric_id": {"type": "string", "minLength": 1},
        "canonical_name": {"type": "string", "minLength": 1},
        "display_name": {"type": "string"},
        "task_type": {
            "type": "string",
            "enum": ["classification", "segmentation", "object_detection",
                    "semantic_segmentation", "instance_segmentation",
                    "change_detection", "point_cloud_segmentation",
                    "point_cloud_change_detection"]
        },
        "direction": {"type": "string", "enum": ["maximize", "minimize"]},
        "formula": {"type": "string", "minLength": 1},
        "formula_hash": {"type": "string"},
        "unit": {"type": "string", "enum": ["fraction", "percent", "scalar"]},
        "class_aggregation": {"type": "string", "enum": ["macro", "micro", "weighted", "none"]},
        "sample_aggregation": {"type": "string", "enum": ["global", "per_batch", "per_tile", "per_scene", "per_cloud_pair"]},
        "ignored_labels": {"type": "array", "items": {"type": "integer"}},
        "included_classes": {"type": "array", "items": {"type": "integer"}},
        "absent_class_policy": {"type": "string", "enum": ["ignore", "zero", "error"]},
        "prediction_level": {"type": "string", "enum": ["point", "voxel", "pixel", "object", "scene", "cloud_pair"]},
        "evaluation_scope": {"type": "string", "enum": ["batch", "crop", "tile", "cylinder", "scene", "full_pc", "full_dataset"]},
    }
}


# Schema for MetricProtocolFingerprint
METRIC_PROTOCOL_FINGERPRINT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "paper_id": {"type": ["string", "null"]},
        "task_type": {"type": ["string", "null"]},
        "dataset_name": {"type": ["string", "null"]},
        "dataset_version": {"type": ["string", "null"]},
        "dataset_subset": {"type": ["string", "null"]},
        "split_name": {"type": ["string", "null"]},
        "split_manifest_hash": {"type": ["string", "null"]},
        "label_mapping_hash": {"type": ["string", "null"]},
        "num_classes": {"type": ["integer", "null"]},
        "included_classes": {"type": ["array", "null"], "items": {"type": "integer"}},
        "excluded_classes": {"type": ["array", "null"], "items": {"type": "integer"}},
        "ignore_index": {"type": ["integer", "null"]},
        "prediction_level": {"type": ["string", "null"]},
        "evaluation_scope": {"type": ["string", "null"]},
        "full_resolution": {"type": ["boolean", "null"]},
        "full_pc": {"type": ["boolean", "null"]},
        "voting_runs": {"type": ["integer", "null"]},
        "interpolation_method": {"type": ["string", "null"]},
        "postprocessing": {"type": ["string", "null"]},
        "metric_id": {"type": ["string", "null"]},
        "formula_hash": {"type": ["string", "null"]},
        "class_aggregation": {"type": ["string", "null"]},
        "sample_aggregation": {"type": ["string", "null"]},
        "checkpoint_selector": {"type": ["string", "null"]},
        "checkpoint_epoch": {"type": ["integer", "null"]},
        "seed_policy": {"type": ["string", "null"]},
        "run_aggregation": {"type": ["string", "null"]},
        "unit": {"type": ["string", "null"]},
    }
}


# Schema for MetricObservation
METRIC_OBSERVATION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["observation_id", "metric_id"],
    "properties": {
        "observation_id": {"type": "string", "minLength": 1},
        "run_id": {"type": ["string", "null"]},
        "metric_id": {"type": "string", "minLength": 1},
        "value": {"type": ["number", "null"]},
        "unit": {"type": "string", "enum": ["fraction", "percent", "scalar"]},
        "protocol_fingerprint": {"type": ["object", "null"]},
        "source_id": {"type": ["string", "null"]},
        "raw_evidence_paths": {"type": "array", "items": {"type": "string"}},
        "computed_at": {"type": "string"},
        "computation_version": {"type": "string"},
        "verification_status": {
            "type": "string",
            "enum": ["MISSING", "DISCOVERED", "UNVERIFIED", "VERIFIED", "RECOMPUTED",
                    "EXACT_MATCH", "COMPARABLE", "WITHIN_TOLERANCE", "VALUE_MISMATCH",
                    "PROTOCOL_MISMATCH", "SOURCE_CONFLICT", "CORRUPTED", "STALE", "SIMULATED"]
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "per_class_values": {"type": ["object", "null"]},
        "std": {"type": ["number", "null"]},
        "n_samples": {"type": ["integer", "null"]},
    }
}


# Schema for MetricSource
METRIC_SOURCE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["source_id", "source_type", "source_role"],
    "properties": {
        "source_id": {"type": "string", "minLength": 1},
        "source_type": {"type": "string"},
        "source_role": {
            "type": "string",
            "enum": ["TARGET_VALUE", "FORMULA_DEFINITION", "DATASET_PROTOCOL",
                    "EVALUATION_PROTOCOL", "RUN_OBSERVATION", "DERIVED_RESULT",
                    "UNVERIFIED_REPORT"]
        },
        "path_or_url": {"type": ["string", "null"]},
        "file_hash": {"type": ["string", "null"]},
        "paper_page": {"type": ["integer", "null"]},
        "paper_table": {"type": ["string", "null"]},
        "table_row": {"type": ["string", "null"]},
        "table_column": {"type": ["string", "null"]},
        "code_symbol": {"type": ["string", "null"]},
        "config_key": {"type": ["string", "null"]},
        "extractor": {"type": ["string", "null"]},
        "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "created_at": {"type": "string"},
    }
}


# Schema for MetricConflict
METRIC_CONFLICT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["conflict_id", "conflict_type", "description"],
    "properties": {
        "conflict_id": {"type": "string", "minLength": 1},
        "conflict_type": {
            "type": "string",
            "enum": ["SAME_VALUE_DIFFERENT_NAMES", "SAME_NAME_DIFFERENT_FORMULA",
                    "REPORT_INCONSISTENT_WITH_RAW", "CSV_INCONSISTENT_WITH_LOGS",
                    "CHECKPOINT_MISMATCH", "UNIT_CONFUSION", "MIOU_VS_MIOU_CH",
                    "VALIDATION_VS_TEST", "SINGLE_VS_MULTI_SEED",
                    "HARDCODED_IN_PLOTTING", "IMAGE_WITHOUT_DATA",
                    "STALE_RUN", "DATA_VERSION_CONFLICT", "CLASS_MAPPING_CONFLICT"]
        },
        "description": {"type": "string"},
        "involved_observations": {"type": "array", "items": {"type": "string"}},
        "involved_sources": {"type": "array", "items": {"type": "string"}},
        "severity": {"type": "string", "enum": ["INFO", "WARNING", "ERROR"]},
        "detected_at": {"type": "string"},
    }
}


def validate_schema(data: dict, schema_name: str) -> tuple[bool, list[str]]:
    """
    Validate data against a schema.
    
    Returns (is_valid, errors).
    """
    import jsonschema

    schema_map = {
        "metric_definition": METRIC_DEFINITION_SCHEMA,
        "metric_protocol_fingerprint": METRIC_PROTOCOL_FINGERPRINT_SCHEMA,
        "metric_observation": METRIC_OBSERVATION_SCHEMA,
        "metric_source": METRIC_SOURCE_SCHEMA,
        "metric_conflict": METRIC_CONFLICT_SCHEMA,
    }

    schema = schema_map.get(schema_name)
    if schema is None:
        return False, [f"Unknown schema: {schema_name}"]

    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except ImportError:
        # jsonschema not available, skip validation
        return True, []


def load_schema(schema_name: str) -> dict:
    """Load a schema by name."""
    schema_map = {
        "metric_definition": METRIC_DEFINITION_SCHEMA,
        "metric_protocol_fingerprint": METRIC_PROTOCOL_FINGERPRINT_SCHEMA,
        "metric_observation": METRIC_OBSERVATION_SCHEMA,
        "metric_source": METRIC_SOURCE_SCHEMA,
        "metric_conflict": METRIC_CONFLICT_SCHEMA,
    }
    return schema_map[schema_name]


def save_schemas(output_dir: Path) -> None:
    """Save all schemas to JSON files."""
    schemas = {
        "metric_definition": METRIC_DEFINITION_SCHEMA,
        "metric_protocol_fingerprint": METRIC_PROTOCOL_FINGERPRINT_SCHEMA,
        "metric_observation": METRIC_OBSERVATION_SCHEMA,
        "metric_source": METRIC_SOURCE_SCHEMA,
        "metric_conflict": METRIC_CONFLICT_SCHEMA,
    }

    for name, schema in schemas.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2))
