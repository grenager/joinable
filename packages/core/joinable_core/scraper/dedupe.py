from __future__ import annotations

import hashlib
import re


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def compute_dedupe_hash(title: str, start_iso: str, venue_name: str | None) -> str:
    parts = [
        normalize_text(title),
        start_iso,
        normalize_text(venue_name or ""),
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
