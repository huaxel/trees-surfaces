"""Validate reference labels against the frozen frame before they reach an estimator.

The plan's protocol asks for four things that a file format can enforce instead of leaving to
discipline: interpretation blinded to the mapped class, a reference definition declared in
advance, unknown as its own category, and disagreements adjudicated against a documented
source hierarchy. A label file that cannot state the first, second and fourth is refused here,
so an unprotocolised pass cannot be estimated from by accident.

The file is one JSON object:

    {
      "schema_version": 1,
      "protocol": {
        "reference_definition": "canopy over the reference line at the point footprint",
        "source_hierarchy": "2021 UrbIS orthophoto, then street-level imagery, then field visit",
        "leaf_on": true,
        "blinded": true
      },
      "labels": [
        {"gid": 266, "chainage_m": 1.0, "label": "canopy",
         "interpreter": "AB", "date": "2026-06-15", "note": ""}
      ]
    }

Labels are joined to the frame on (gid, chainage_m), the same key the selection records, and a
chainage that is not a frame candidate is refused rather than snapped to the nearest point:
snapping would silently move a label, which is the failure mode the sampling plan exists to
measure.
"""
import datetime
import json
from pathlib import Path

from estimate import CANOPY, LABELS, NOT_CANOPY, UNKNOWN
from metrics import require

SCHEMA_VERSION = 1
PROTOCOL_FIELDS = ('reference_definition', 'source_hierarchy', 'leaf_on', 'blinded')
LABEL_FIELDS = ('gid', 'chainage_m', 'label', 'interpreter', 'date')
OPTIONAL_FIELDS = ('note',)
CHAINAGE_TOLERANCE = 1e-6


def _frame_keys(frame):
    return {(point['gid'], round(point['chainage_m'], 6)) for point in frame['points']}


def _validate_protocol(protocol):
    require(isinstance(protocol, dict), 'label file has no protocol block')
    for field in PROTOCOL_FIELDS:
        require(field in protocol, f'protocol is missing {field}')
    for field in ('reference_definition', 'source_hierarchy'):
        require(isinstance(protocol[field], str) and protocol[field].strip(),
                f'protocol {field} must be a non-empty statement, not a placeholder')
    require(protocol['leaf_on'] is True,
            'protocol leaf_on must be true: canopy presence recorded off-season is not the '
            'estimand, and the plan requires leaf-on interpretation')
    require(protocol['blinded'] is True,
            'protocol blinded must be true: interpreters must not see the mapped class')
    return {field: protocol[field] for field in PROTOCOL_FIELDS}


def _validate_label(record, keys):
    require(isinstance(record, dict), f'label entry is not an object: {record!r}')
    unknown_fields = set(record) - set(LABEL_FIELDS) - set(OPTIONAL_FIELDS)
    require(not unknown_fields, f'label entry has unrecognised fields: {sorted(unknown_fields)}')
    for field in LABEL_FIELDS:
        require(field in record, f'label entry is missing {field}: {record!r}')
    require(isinstance(record['gid'], int), f'gid must be an integer: {record["gid"]!r}')
    require(isinstance(record['chainage_m'], (int, float)) and not isinstance(record['chainage_m'], bool),
            f'chainage_m must be a number: {record["chainage_m"]!r}')
    key = (record['gid'], round(float(record['chainage_m']), 6))
    require(key in keys,
            f'label at {key} is not a frame candidate: refusing to snap it to the nearest point')
    require(record['label'] in LABELS,
            f'unrecognised label {record["label"]!r}; expected one of {list(LABELS)}')
    require(isinstance(record['interpreter'], str) and record['interpreter'].strip(),
            'label entry needs an interpreter identifier')
    try:
        datetime.date.fromisoformat(str(record['date']))
    except ValueError:
        raise ValueError(f'date must be ISO YYYY-MM-DD: {record["date"]!r}') from None
    return key, record['label']


def load_labels(path, frame):
    """Read and validate a label file. Returns labels keyed by (gid, chainage_m)."""
    document = json.loads(Path(path).read_text())
    require(isinstance(document, dict), 'label file must contain a JSON object')
    require(document.get('schema_version') == SCHEMA_VERSION,
            f'label file schema_version must be {SCHEMA_VERSION}')
    protocol = _validate_protocol(document.get('protocol'))
    records = document.get('labels')
    require(isinstance(records, list), 'label file has no labels list')
    keys = _frame_keys(frame)
    labels, seen = {}, set()
    for record in records:
        key, label = _validate_label(record, keys)
        require(key not in seen, f'duplicate label for {key}')
        seen.add(key)
        labels[key] = label
    return dict(labels=labels, protocol=protocol, labelled=len(labels),
                unknown=sum(1 for label in labels.values() if label == UNKNOWN),
                frame_candidates=len(keys))


def coverage(frame, labels):
    """How much of each stratum is labelled, so a partial pass is visible rather than assumed."""
    totals, done = {}, {}
    for point in frame['points']:
        if point['stratum'] not in totals:
            totals[point['stratum']] = 0
            done[point['stratum']] = 0
        totals[point['stratum']] += 1
        if (point['gid'], round(point['chainage_m'], 6)) in labels:
            done[point['stratum']] += 1
    return {name: dict(labelled=done[name], candidates=totals[name],
                       fraction=round(done[name]/totals[name], 6))
            for name in sorted(totals)}


def template(frame, sample):
    """A label file skeleton for a drawn sample: protocol placeholders must be filled."""
    return dict(schema_version=SCHEMA_VERSION,
                protocol={field: (False if field in ('leaf_on', 'blinded') else '')
                          for field in PROTOCOL_FIELDS},
                labels=[dict(gid=row['gid'], chainage_m=row['chainage_m'], label=UNKNOWN,
                             interpreter='', date='') for row in sample])
