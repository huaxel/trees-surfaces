#!/usr/bin/env python3
"""Integration-test review preservation and deliberate reset flags in copies."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAKEHOLDER_REVIEW_FIELDS = (
    "review_status", "reviewer_name", "reviewer_role", "reviewed_at",
    "accepted_decision_question", "accepted_spatial_unit", "accepted_mobility_measure",
    "accepted_heat_period", "false_positive_preference", "evidence_threshold", "review_notes",
)
IMAGE_REVIEW_FIELDS = ("facade_observation", "structural_observation", "reviewer", "reviewed_at", "confidence")
STRUCTURAL_REVIEW_FIELDS = ("structural_observation", "reviewer", "reviewed_at", "confidence")
REGISTER_REVIEW_FIELDS = ("register_decision", "register_observation", "reviewer", "reviewed_at", "confidence")


def update_first_row(path: Path, values: dict[str, str]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    if not fields or not rows:
        raise AssertionError(f"worksheet is empty: {path}")
    rows[0].update(values)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True, capture_output=True, text=True)


def run_fails(*args: str, message: str) -> None:
    result = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if result.returncode == 0 or message not in result.stderr:
        raise AssertionError(f"expected failure containing {message!r}: {result.stderr}")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_unchanged(expected: dict[Path, bytes]) -> None:
    changed = [path for path, content in expected.items() if path.read_bytes() != content]
    if changed:
        raise AssertionError(f"failed regeneration modified review artifacts: {changed}")


def record_count(path: Path) -> int:
    return json.loads(path.read_text(encoding="utf-8"))["record_count"]


def csv_rows_without(path: Path, excluded_fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {field: value for field, value in row.items() if field not in excluded_fields}
            for row in csv.DictReader(handle)
        ]


def require_blank(path: Path, fields: tuple[str, ...]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if any(row[field] for row in rows for field in fields):
        raise AssertionError(f"reset left completed review fields in {path}")


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        trees = temp / "trees-data"
        ages = temp / "ages-data"
        shutil.copytree(ROOT / "trees-surfaces" / "data", trees)
        shutil.copytree(ROOT / "three-ages" / "data", ages)

        stakeholder = trees / "tree-stakeholder-review.csv"
        with stakeholder.open(newline="", encoding="utf-8") as handle:
            proposal = next(csv.DictReader(handle))
        update_first_row(stakeholder, {
            "review_status": "accepted",
            "reviewer_name": "Integration Test",
            "reviewer_role": "Reviewer",
            "reviewed_at": "2026-09-20",
            "accepted_decision_question": proposal["decision_question"],
            "accepted_spatial_unit": proposal["spatial_unit"],
            "accepted_mobility_measure": proposal["mobility_measure"],
            "accepted_heat_period": "2016-08-24",
            "false_positive_preference": "Prefer manual follow-up",
            "evidence_threshold": "One additional check",
            "review_notes": "Preservation and reset integration test",
        })
        update_first_row(ages / "three-ages-image-review.csv", {
            "facade_observation": "Test facade observation",
            "reviewer": "Integration Test",
            "reviewed_at": "2026-09-20",
            "confidence": "medium",
        })
        update_first_row(ages / "three-ages-structural-review.csv", {
            "structural_observation": "Test structural observation",
            "reviewer": "Integration Test",
            "reviewed_at": "2026-09-20",
            "confidence": "medium",
        })
        update_first_row(ages / "three-ages-register-review.csv", {
            "register_decision": "retain as reconstruction evidence",
            "register_observation": "Test register observation",
            "reviewer": "Integration Test",
            "reviewed_at": "2026-09-20",
            "confidence": "medium",
        })

        run(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"), "--data-dir", str(trees))
        run(str(ROOT / "three-ages" / "export_pilot.py"), "--data-dir", str(ages))
        expected_completed = (
            trees / "tree-stakeholder-reviews.json",
            ages / "three-ages-image-reviews.json",
            ages / "three-ages-structural-reviews.json",
            ages / "three-ages-register-reviews.json",
        )
        if any(record_count(path) != 1 for path in expected_completed):
            raise AssertionError("ordinary regeneration did not preserve every completed review")

        stakeholder_outputs = (
            stakeholder,
            trees / "tree-stakeholder-reviews.json",
        )
        stakeholder_before = {path: path.read_bytes() for path in stakeholder_outputs}
        sensitivity_path = trees / "tree-signal-sensitivity.json"
        sensitivity_original = sensitivity_path.read_bytes()
        sensitivity = json.loads(sensitivity_original)
        sensitivity["weight_sensitivity"]["interpretation"] = "Changed integration-test evidence"
        write_json(sensitivity_path, sensitivity)
        run_fails(
            str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"),
            "--data-dir", str(trees),
            message="proposal evidence changed",
        )
        require_unchanged(stakeholder_before)
        sensitivity_path.write_bytes(sensitivity_original)

        review_outputs = (
            ages / "three-ages-pilot-export.csv",
            ages / "three-ages-image-review.csv",
            ages / "three-ages-image-reviews.json",
            ages / "three-ages-structural-review.csv",
            ages / "three-ages-structural-reviews.json",
            ages / "three-ages-register-review.csv",
            ages / "three-ages-register-reviews.json",
        )
        reviews_before = {path: path.read_bytes() for path in review_outputs}
        pilot_path = ages / "three-ages-pilot.json"
        pilot_original = pilot_path.read_bytes()
        pilot = json.loads(pilot_original)
        pilot["records"][0]["image_evidence"][0]["source_url"] += "?changed=1"
        write_json(pilot_path, pilot)
        run_fails(
            str(ROOT / "three-ages" / "export_pilot.py"),
            "--data-dir", str(ages),
            message="after provenance changed",
        )
        require_unchanged(reviews_before)
        pilot_path.write_bytes(pilot_original)

        crops_path = ages / "three-ages-structural-crops.json"
        crops_original = crops_path.read_bytes()
        crops = json.loads(crops_original)
        crops["records"][0]["assets"][0]["pixel_sha256"] = "changed-integration-test-hash"
        write_json(crops_path, crops)
        run_fails(
            str(ROOT / "three-ages" / "export_pilot.py"),
            "--data-dir", str(ages),
            message="after provenance changed",
        )
        require_unchanged(reviews_before)
        crops_path.write_bytes(crops_original)

        pilot = json.loads(pilot_original)
        pilot["records"][0]["register"]["source_comparison"] = "Changed integration-test comparison"
        write_json(pilot_path, pilot)
        run_fails(
            str(ROOT / "three-ages" / "export_pilot.py"),
            "--data-dir", str(ages),
            message="after provenance changed",
        )
        require_unchanged(reviews_before)
        pilot_path.write_bytes(pilot_original)

        reset_contracts = (
            (stakeholder, STAKEHOLDER_REVIEW_FIELDS),
            (ages / "three-ages-image-review.csv", IMAGE_REVIEW_FIELDS + ("annotation_status",)),
            (ages / "three-ages-structural-review.csv", STRUCTURAL_REVIEW_FIELDS + ("annotation_status",)),
            (ages / "three-ages-register-review.csv", REGISTER_REVIEW_FIELDS + ("annotation_status",)),
        )
        source_fields_before_reset = {
            path: csv_rows_without(path, mutable_fields)
            for path, mutable_fields in reset_contracts
        }
        run(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"), "--data-dir", str(trees), "--reset-review")
        run(str(ROOT / "three-ages" / "export_pilot.py"), "--data-dir", str(ages), "--reset-reviews")
        if any(record_count(path) != 0 for path in expected_completed):
            raise AssertionError("explicit reset left a compiled completed review")

        for path, mutable_fields in reset_contracts:
            if csv_rows_without(path, mutable_fields) != source_fields_before_reset[path]:
                raise AssertionError(f"reset changed source-derived worksheet fields in {path}")
        require_blank(stakeholder, STAKEHOLDER_REVIEW_FIELDS)
        require_blank(ages / "three-ages-image-review.csv", IMAGE_REVIEW_FIELDS)
        require_blank(ages / "three-ages-structural-review.csv", STRUCTURAL_REVIEW_FIELDS)
        require_blank(ages / "three-ages-register-review.csv", REGISTER_REVIEW_FIELDS)

    print("review preservation, provenance refusal and explicit reset integration passed")


if __name__ == "__main__":
    main()
