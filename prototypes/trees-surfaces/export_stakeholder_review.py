#!/usr/bin/env python3
"""Generate and preserve the Trees & Surfaces stakeholder review worksheet."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

FIELDS = [
    "proposal_id",
    "proposal_status",
    "proposed_stakeholder",
    "decision_question",
    "spatial_unit",
    "heat_measure",
    "mobility_measure",
    "measured_flow_context",
    "output_boundary",
    "core_join_summary",
    "sensitivity_summary",
    "review_status",
    "reviewer_name",
    "reviewer_role",
    "reviewed_at",
    "accepted_decision_question",
    "accepted_spatial_unit",
    "accepted_mobility_measure",
    "accepted_heat_period",
    "false_positive_preference",
    "evidence_threshold",
    "review_notes",
]
REVIEW_FIELDS = [
    "review_status",
    "reviewer_name",
    "reviewer_role",
    "reviewed_at",
    "accepted_decision_question",
    "accepted_spatial_unit",
    "accepted_mobility_measure",
    "accepted_heat_period",
    "false_positive_preference",
    "evidence_threshold",
    "review_notes",
]
COMMON_REQUIRED_REVIEW_FIELDS = [
    "review_status",
    "reviewer_name",
    "reviewer_role",
    "reviewed_at",
    "false_positive_preference",
    "evidence_threshold",
    "review_notes",
]
ACCEPTED_DECISION_FIELDS = [
    "accepted_decision_question",
    "accepted_spatial_unit",
    "accepted_mobility_measure",
    "accepted_heat_period",
]
ACCEPTED_STATUSES = {"accepted", "accepted with changes"}
PROVENANCE_FIELDS = [field for field in FIELDS if field not in REVIEW_FIELDS]
SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
ESCAPED_FIELDS_COLUMN = "_spreadsheet_escaped_fields"


def text(value: object) -> str:
    return "" if value is None else str(value)


def spreadsheet_formula_payload(value: str) -> bool:
    return value.startswith(SPREADSHEET_FORMULA_PREFIXES)


def spreadsheet_safe(value: object) -> str:
    string_value = text(value)
    return f"'{string_value}" if spreadsheet_formula_payload(string_value) else string_value


def spreadsheet_unescape(value: str) -> str:
    if not value.startswith("'") or not spreadsheet_formula_payload(value[1:]):
        raise RuntimeError("stakeholder worksheet escape metadata does not match its cell value")
    return value[1:]


def read_existing(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, strict=True)
            fields = reader.fieldnames or []
            if len(set(fields)) != len(fields):
                raise RuntimeError("existing stakeholder worksheet contains duplicate columns")
            required = {"proposal_id", *REVIEW_FIELDS}
            missing = required - set(fields)
            if missing:
                raise RuntimeError(f"existing stakeholder worksheet is missing required columns: {sorted(missing)}")
            rows = list(reader)
    except csv.Error as error:
        raise RuntimeError(f"existing stakeholder worksheet is malformed CSV: {error}") from error
    if len(rows) != 1:
        raise RuntimeError(f"stakeholder worksheet must contain exactly one proposal row, found {len(rows)}")
    row = rows[0]
    serialized_escape_map = row.pop(ESCAPED_FIELDS_COLUMN, "")
    try:
        escape_map = json.loads(serialized_escape_map) if serialized_escape_map else {}
    except json.JSONDecodeError as error:
        raise RuntimeError("stakeholder worksheet contains malformed spreadsheet escape metadata") from error
    if not isinstance(escape_map, dict) or not all(isinstance(field, str) and isinstance(value, str) for field, value in escape_map.items()):
        raise RuntimeError("stakeholder worksheet spreadsheet escape metadata must be a string map")
    unknown_escaped_fields = set(escape_map) - set(FIELDS)
    if unknown_escaped_fields:
        raise RuntimeError(f"stakeholder worksheet has escape metadata for unknown columns: {sorted(unknown_escaped_fields)}")
    for field, escaped_value in escape_map.items():
        if row.get(field, "") == escaped_value:
            row[field] = spreadsheet_unescape(escaped_value)
    return row


def validate_review(row: dict[str, object], allowed_statuses: set[str]) -> None:
    values = {field: text(row.get(field)).strip() for field in REVIEW_FIELDS}
    if not any(values.values()):
        return
    for field in COMMON_REQUIRED_REVIEW_FIELDS:
        if not values[field]:
            raise RuntimeError(f"stakeholder review is missing {field}")
    if values["review_status"] not in allowed_statuses:
        raise RuntimeError(f"invalid stakeholder review status: {values['review_status']!r}")
    if values["review_status"] in ACCEPTED_STATUSES:
        for field in ACCEPTED_DECISION_FIELDS:
            if not values[field]:
                raise RuntimeError(f"accepted stakeholder review is missing {field}")
    try:
        datetime.fromisoformat(values["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError("stakeholder reviewed_at must be ISO 8601") from error


def preserve_review(
    generated: dict[str, object],
    existing: dict[str, str] | None,
    allowed_statuses: set[str],
) -> dict[str, object]:
    if not existing or not any(existing.get(field, "").strip() for field in REVIEW_FIELDS):
        validate_review(generated, allowed_statuses)
        return generated
    if existing.get("proposal_id") != text(generated.get("proposal_id")):
        raise RuntimeError("refusing to move stakeholder review onto a different proposal")
    mismatches = [field for field in PROVENANCE_FIELDS if existing.get(field, "") != text(generated.get(field))]
    if mismatches:
        raise RuntimeError(f"refusing to attach stakeholder review after proposal evidence changed: {mismatches}")
    generated.update({field: existing.get(field, "") for field in REVIEW_FIELDS})
    validate_review(generated, allowed_statuses)
    return generated


def write_csv(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=[*FIELDS, ESCAPED_FIELDS_COLUMN], lineterminator="\n")
        writer.writeheader()
        escaped_fields = [field for field in FIELDS if spreadsheet_formula_payload(text(row.get(field, "")))]
        output_row = {field: spreadsheet_safe(row.get(field, "")) for field in FIELDS}
        escape_map = {field: output_row[field] for field in escaped_fields}
        output_row[ESCAPED_FIELDS_COLUMN] = json.dumps(escape_map, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        writer.writerow(output_row)
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def promote_review_artifacts(stage: Path, data: Path, filenames: tuple[str, ...], replace_file=os.replace) -> None:
    with tempfile.TemporaryDirectory(prefix=".review-backup-", dir=data.parent) as temporary:
        backup = Path(temporary)
        existing = set()
        for filename in filenames:
            destination = data / filename
            if destination.is_file():
                shutil.copy2(destination, backup / filename)
                existing.add(filename)

        promoted = []
        try:
            for filename in filenames:
                replace_file(stage / filename, data / filename)
                promoted.append(filename)
        except BaseException:
            for filename in reversed(promoted):
                destination = data / filename
                if filename in existing:
                    os.replace(backup / filename, destination)
                else:
                    destination.unlink(missing_ok=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--reset-review", action="store_true", help="deliberately clear the stakeholder review fields")
    args = parser.parse_args()

    data = args.data_dir
    proposal = json.loads((data / "tree-stakeholder-proposal.json").read_text(encoding="utf-8"))
    sensitivity = json.loads((data / "tree-signal-sensitivity.json").read_text(encoding="utf-8"))
    audit = sensitivity["data_completeness"]
    weights = sensitivity["weight_sensitivity"]
    allowed_statuses = set(proposal["allowed_review_statuses"])
    row: dict[str, object] = {
        "proposal_id": proposal["proposal_id"],
        "proposal_status": proposal["status"],
        "proposed_stakeholder": proposal["proposed_stakeholder"],
        "decision_question": proposal["decision_question"],
        "spatial_unit": proposal["spatial_unit"],
        "heat_measure": proposal["heat_measure"],
        "mobility_measure": proposal["mobility_measure"],
        "measured_flow_context": proposal["measured_flow_context"],
        "output_boundary": proposal["output_boundary"],
        "core_join_summary": (
            f"{audit['analyzed_records']}/{audit['managed_records']} records analyzed; "
            f"{len(audit['missing_coordinate_ids'])} missing coordinates; "
            f"{len(audit['heat_nodata_ids'])} NoData heat pixels; "
            f"{len(audit['analysis_unmatched_ids'])} unmatched core joins; "
            f"{audit['measured_flow_context_records']}/{audit['managed_records']} with measured-flow history"
        ),
        "sensitivity_summary": (
            f"balanced top ten overlaps {weights['heat_only_top_10_overlap']}/10 with heat-only and "
            f"{weights['proximity_only_top_10_overlap']}/10 with proximity-only; {weights['interpretation']}"
        ),
        **{field: "" for field in REVIEW_FIELDS},
    }
    output = data / "tree-stakeholder-review.csv"
    compiled_output = data / "tree-stakeholder-reviews.json"
    existing = None if args.reset_review else read_existing(output)
    row = preserve_review(row, existing, allowed_statuses)
    completed = any(text(row.get(field)).strip() for field in REVIEW_FIELDS)
    compiled = {
        "source": output.name,
        "proposal_id": proposal["proposal_id"],
        "status": "completed stakeholder review" if completed else "stakeholder review pending",
        "record_count": 1 if completed else 0,
        "records": [{field: text(row[field]) for field in FIELDS}] if completed else [],
    }
    artifact_names = (output.name, compiled_output.name)
    with tempfile.TemporaryDirectory(prefix=".review-stage-", dir=data.parent) as temporary:
        stage = Path(temporary)
        write_csv(stage / output.name, row)
        write_json(stage / compiled_output.name, compiled)
        promote_review_artifacts(stage, data, artifact_names)
    try:
        display_output = output.relative_to(ROOT)
        display_compiled = compiled_output.relative_to(ROOT)
    except ValueError:
        display_output, display_compiled = output, compiled_output
    print(f"wrote {display_output} and {display_compiled}")
    if completed:
        print("preserved one completed stakeholder review")


if __name__ == "__main__":
    main()
