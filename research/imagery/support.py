"""Shared assertions, digests and canonical JSON for the imagery diagnostics."""
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def digest_bytes(body, algorithm='sha256'):
    return hashlib.new(algorithm, body).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
