"""Load and validate the two inputs: a draft (Markdown with front matter) and fact sheets (JSON).

Validation is strict on purpose. A fact without a source is rejected, because the whole
point of the tool is that every number shown to donors traces back to something a person
can check.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .models import Draft, Fact, InputError

KINDS = {"money", "count", "percent"}
COMPARATORS = {"exact", "at_least"}
TYPES = {"achievement", "goal", "context"}
REQUIRED_FACT_FIELDS = ["id", "statement", "value", "kind", "source"]


def load_draft(path: str) -> Draft:
    p = Path(path)
    if not p.is_file():
        raise InputError(f"Draft not found: {path}")
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()

    meta: Dict[str, str] = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        try:
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration:
            raise InputError(f"{path}: front matter starts with '---' but never closes")
        for raw in lines[1:end]:
            if ":" in raw:
                key, val = raw.split(":", 1)
                meta[key.strip()] = val.strip()
        body_start = end + 1

    for key in ("voice", "featured_org"):
        if not meta.get(key):
            raise InputError(
                f"{path}: front matter is missing '{key}'. "
                "The checker needs to know who is publishing and who the post is about."
            )

    body = lines[body_start:]
    if not any(line.strip() for line in body):
        raise InputError(f"{path}: the draft has no body text to check")

    return Draft(
        path=str(path),
        title=meta.get("title", p.stem),
        voice=meta["voice"],
        featured_org=meta["featured_org"],
        lines=body,
        body_start_line=body_start + 1,
    )


def load_fact_sheet(path: str) -> List[Fact]:
    p = Path(path)
    if not p.is_file():
        raise InputError(f"Fact sheet not found: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise InputError(f"{path}: not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}")

    org_id = data.get("org_id")
    if not org_id:
        raise InputError(f"{path}: missing 'org_id'")
    raw_facts = data.get("facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        raise InputError(f"{path}: 'facts' must be a non-empty list")

    facts: List[Fact] = []
    seen = set()
    for i, f in enumerate(raw_facts, start=1):
        label = f"{path}: fact #{i} ({f.get('id', 'no id')})"
        missing = [k for k in REQUIRED_FACT_FIELDS if f.get(k) in (None, "")]
        if missing:
            raise InputError(f"{label} is missing {', '.join(missing)}. Every fact needs a value and a source.")
        if f["kind"] not in KINDS:
            raise InputError(f"{label}: kind must be one of {sorted(KINDS)}, got '{f['kind']}'")
        comparator = f.get("comparator", "exact")
        if comparator not in COMPARATORS:
            raise InputError(f"{label}: comparator must be one of {sorted(COMPARATORS)}")
        ftype = f.get("type", "context")
        if ftype not in TYPES:
            raise InputError(f"{label}: type must be one of {sorted(TYPES)}")
        if not isinstance(f["value"], (int, float)) or isinstance(f["value"], bool):
            raise InputError(f"{label}: value must be a number")
        fid = f"{org_id}:{f['id']}"
        if fid in seen:
            raise InputError(f"{label}: duplicate fact id '{f['id']}'")
        seen.add(fid)
        facts.append(Fact(
            id=fid,
            org_id=org_id,
            org_name=data.get("org_name", org_id),
            statement=f["statement"],
            value=float(f["value"]),
            kind=f["kind"],
            comparator=comparator,
            type=ftype,
            keywords=[k.lower() for k in f.get("keywords", [])],
            source=f["source"],
        ))
    return facts


def load_inputs(draft_path: str, fact_paths: List[str]):
    draft = load_draft(draft_path)
    facts: List[Fact] = []
    for fp in fact_paths:
        facts.extend(load_fact_sheet(fp))
    loaded_orgs = {f.org_id for f in facts}
    if draft.featured_org not in loaded_orgs:
        raise InputError(
            f"The draft features '{draft.featured_org}', but no fact sheet for that org was loaded "
            f"(loaded: {', '.join(sorted(loaded_orgs))}). Checking against the wrong org's facts "
            "would give false results, so nothing was checked."
        )
    return draft, facts
