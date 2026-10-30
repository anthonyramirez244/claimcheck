"""Data shapes shared across the pipeline.

Everything is a plain dataclass so the JSON report is just `asdict()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Statuses that stop a draft from being marked ready to publish.
BLOCKING = {"MISMATCH", "UNSUPPORTED", "ATTRIBUTION", "NEEDS_REVIEW"}


class InputError(Exception):
    """Raised for bad input. The CLI turns it into exit code 2 and a clear message."""


@dataclass
class Fact:
    """One verified fact from a nonprofit's fact sheet. Every fact needs a source."""
    id: str            # globally unique, "<org_id>:<local id>", e.g. "harbor-pathways:f1"
    org_id: str        # who the fact belongs to
    org_name: str
    statement: str     # human-readable sentence shown in the report
    value: float
    kind: str          # "money" | "count" | "percent"
    comparator: str    # "exact" or "at_least" (source itself says "more than N")
    type: str          # "achievement" (past result) | "goal" | "context"
    keywords: List[str]
    source: str        # where a reviewer can confirm it


@dataclass
class Draft:
    path: str
    title: str
    voice: str          # org id of whoever is publishing the copy
    featured_org: str   # org id the copy is about
    lines: List[str]    # body lines, front matter removed
    body_start_line: int  # 1-based line number of the first body line in the file


@dataclass
class Claim:
    """A number found in the draft, plus the words around it that change its meaning."""
    id: str
    literal: str        # text as written, qualifier included, e.g. "more than 500"
    value: float
    kind: str
    qualifier: str      # "exact" | "at_least" | "approx" | "nearly"
    precision: float    # size of the last written digit: "2.3 million" -> 100000, "25K" -> 1000, "450" -> 0 (exact)
    sentence: str
    context: str        # the clause around the number; used for matching so two numbers in one sentence don't share context
    line: int


@dataclass
class Result:
    claim: Claim
    status: str                       # SUPPORTED | WARNING | MISMATCH | UNSUPPORTED | ATTRIBUTION | NEEDS_REVIEW
    fact: Optional[Fact] = None
    notes: List[str] = field(default_factory=list)
    candidates: List[str] = field(default_factory=list)  # fact ids, when ambiguous
    matched_by: str = "rules"         # "rules" or "model"

    @property
    def blocking(self) -> bool:
        return self.status in BLOCKING
