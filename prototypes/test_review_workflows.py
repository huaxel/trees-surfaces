#!/usr/bin/env python3
"""Integration-test Trees & Surfaces stakeholder review preservation and deliberate reset flags in copies."""
from __future__ import annotations

import csv
import json
import os
import runpy
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
        shutil.copytree(ROOT / "trees-surfaces" / "data", trees)

        stakeholder = trees / "tree-stakeholder-review.csv"
        with stakeholder.open(newline="", encoding="utf-8") as handle:
            proposal = next(csv.DictReader(handle))
        update_first_row(stakeholder, {
            "review_status": "accepted",
            "reviewer_name": "Integration Test",
            "reviewer_role": "=Reviewer",
            "reviewed_at": "2026-09-20",
            "accepted_decision_question": proposal["decision_question"],
            "accepted_spatial_unit": proposal["spatial_unit"],
            "accepted_mobility_measure": proposal["mobility_measure"],
            "accepted_heat_period": "2016-08-24",
            "false_positive_preference": "Prefer manual follow-up",
            "evidence_threshold": "One additional check",
            "review_notes": "'=HYPERLINK(\"https://example.invalid\",\"review\")",
        })

        run(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"), "--data-dir", str(trees))
        expected_completed = (
            trees / "tree-stakeholder-reviews.json",
        )
        if any(record_count(path) != 1 for path in expected_completed):
            raise AssertionError("ordinary regeneration did not preserve completed stakeholder review")
        with stakeholder.open(newline="", encoding="utf-8") as handle:
            persisted_review = next(csv.DictReader(handle))
        if not persisted_review["reviewer_role"].startswith("'="):
            raise AssertionError("stakeholder worksheet did not neutralize a spreadsheet formula")
        if not persisted_review["review_notes"].startswith("'="):
            raise AssertionError("stakeholder worksheet did not preserve an apostrophe-leading formula value")
        if json.loads(persisted_review.get("_spreadsheet_escaped_fields", "{}")) != {"reviewer_role": "'=Reviewer"}:
            raise AssertionError("stakeholder worksheet did not record escaped formula cells")
        compiled_review = json.loads(expected_completed[0].read_text(encoding="utf-8"))["records"][0]
        if compiled_review["reviewer_role"] != "=Reviewer":
            raise AssertionError("compiled review did not restore the original formula-like text")
        if not compiled_review["review_notes"].startswith("'=HYPERLINK"):
            raise AssertionError("compiled review did not preserve the original apostrophe-leading text")

        update_first_row(stakeholder, {
            "reviewer_role": "Stakeholder",
            "review_notes": "'=Revised literal text",
        })
        run(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"), "--data-dir", str(trees))
        with stakeholder.open(newline="", encoding="utf-8") as handle:
            edited_review = next(csv.DictReader(handle))
        if json.loads(edited_review.get("_spreadsheet_escaped_fields", "{}")):
            raise AssertionError("stale escape metadata survived an ordinary human edit")
        compiled_review = json.loads(expected_completed[0].read_text(encoding="utf-8"))["records"][0]
        if compiled_review["reviewer_role"] != "Stakeholder" or compiled_review["review_notes"] != "'=Revised literal text":
            raise AssertionError("stale escape metadata altered edited review text")

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

        proposal_path = trees / "tree-stakeholder-proposal.json"
        proposal_original = proposal_path.read_bytes()
        proposal = json.loads(proposal_original)
        proposal["decision_question"] = "Changed integration-test decision question"
        write_json(proposal_path, proposal)
        run_fails(
            str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"),
            "--data-dir", str(trees),
            message="proposal evidence changed",
        )
        require_unchanged(stakeholder_before)
        proposal_path.write_bytes(proposal_original)

        reset_contracts = (
            (stakeholder, (*STAKEHOLDER_REVIEW_FIELDS, "_spreadsheet_escaped_fields")),
        )
        source_fields_before_reset = {
            path: csv_rows_without(path, mutable_fields)
            for path, mutable_fields in reset_contracts
        }
        run(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"), "--data-dir", str(trees), "--reset-review")
        if any(record_count(path) != 0 for path in expected_completed):
            raise AssertionError("explicit reset left a compiled completed review")

        for path, mutable_fields in reset_contracts:
            if csv_rows_without(path, mutable_fields) != source_fields_before_reset[path]:
                raise AssertionError(f"reset changed source-derived worksheet fields in {path}")
        require_blank(stakeholder, STAKEHOLDER_REVIEW_FIELDS)

        promotion_root = temp / "promotion-rollback"
        stage = promotion_root / "stage"
        destination = promotion_root / "data"
        stage.mkdir(parents=True)
        destination.mkdir()
        filenames = ("tree-stakeholder-review.csv", "tree-stakeholder-reviews.json")
        for filename in filenames:
            (stage / filename).write_text(f"new-{filename}", encoding="utf-8")
            (destination / filename).write_text(f"old-{filename}", encoding="utf-8")
        calls = 0

        def fail_second_replace(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated review promotion failure")
            os.replace(source, target)

        exporter = runpy.run_path(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"))
        try:
            exporter["promote_review_artifacts"](stage, destination, filenames, fail_second_replace)
        except OSError as error:
            if str(error) != "simulated review promotion failure":
                raise
        else:
            raise AssertionError("review artifact promotion did not propagate a rename failure")
        if any((destination / filename).read_text(encoding="utf-8") != f"old-{filename}" for filename in filenames):
            raise AssertionError("review artifact promotion failure left CSV and JSON inconsistent")

    print("stakeholder review preservation, provenance refusal, reset and rollback integration passed")


if __name__ == "__main__":
    main()
