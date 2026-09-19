#!/usr/bin/env python3
"""Generate and preserve the Trees & Surfaces stakeholder review worksheet."""
from __future__ import annotations

import argparse
import csv
import json
import os
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


def text(value: object) -> str:
    return "" if value is None else str(value)


def read_existing(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"proposal_id", *REVIEW_FIELDS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"existing stakeholder worksheet is missing required columns: {sorted(missing)}")
        rows = list(reader)
    if len(rows) != 1:
        raise RuntimeError(f"stakeholder worksheet must contain exactly one proposal row, found {len(rows)}")
    return rows[0]


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
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
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
    write_csv(output, row)
    completed = any(text(row.get(field)).strip() for field in REVIEW_FIELDS)
    write_json(compiled_output, {
        "source": output.name,
        "proposal_id": proposal["proposal_id"],
        "status": "completed stakeholder review" if completed else "stakeholder review pending",
        "record_count": 1 if completed else 0,
        "records": [{field: text(row[field]) for field in FIELDS}] if completed else [],
    })
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
