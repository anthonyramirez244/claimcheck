"""Tie each claim to a fact, then verify the number with plain arithmetic.

Two separate questions, answered separately:
  1. Which fact is this sentence talking about?  (keyword overlap; the model may help later)
  2. Does the number agree with that fact?        (always code, never the model)
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import Claim, Draft, Fact, Result

APPROX_TOLERANCE = 0.05   # "about 450" may be within 5% of the source
NEARLY_TOLERANCE = 0.10   # "nearly 40" may be at most 10% above the source, never below
FIRST_PERSON = re.compile(r"\b(we|we've|we're|we'll|we'd|our|ours|us)\b", re.IGNORECASE)


def _norm_words(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    # crude plural strip so "employers" matches the keyword "employer"
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words]


def keyword_score(fact: Fact, sentence: str) -> int:
    padded = " " + " ".join(_norm_words(sentence)) + " "
    return sum(1 for k in fact.keywords if " " + " ".join(_norm_words(k)) + " " in padded)


def _fmt(v: float, kind: str) -> str:
    s = f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"
    return {"money": f"${s}", "percent": f"{s}%"}.get(kind, s)


def compare(claim: Claim, fact: Fact) -> Tuple[str, str]:
    """Return (status, note) for one claim checked against one fact."""
    C, F, q = claim.value, fact.value, claim.qualifier
    src = ("more than " if fact.comparator == "at_least" else "") + _fmt(F, fact.kind)

    if fact.comparator == "exact":
        if q == "exact":
            if C == F:
                return "SUPPORTED", ""
            if claim.precision and abs(C - F) <= claim.precision / 2:
                return "SUPPORTED", f"Rounded from {src}."
            return "MISMATCH", f"Source says {src}."
        if q == "at_least":
            return ("SUPPORTED", "") if F >= C else ("MISMATCH", f"Source says {src}, which is not more than {_fmt(C, claim.kind)}.")
        if q == "approx":
            return ("SUPPORTED", "") if abs(C - F) <= APPROX_TOLERANCE * F else ("MISMATCH", f"Source says {src}; 'about' allows {APPROX_TOLERANCE:.0%}.")
        if q == "nearly":
            ok = F <= C and (C - F) <= NEARLY_TOLERANCE * C
            return ("SUPPORTED", "") if ok else ("MISMATCH", f"Source says {src}; 'nearly' must be slightly above the real number.")

    # The source itself only says "more than F", so the true value is unknown above F.
    if q == "at_least":
        return ("SUPPORTED", "") if C <= F else ("MISMATCH", f"Source only supports {src}.")
    if C <= F:
        return "WARNING", f"Source says {src}; the draft drops the 'more than'."
    return "MISMATCH", f"Source only supports {src}."


def match_claim(claim: Claim, facts: List[Fact]) -> Result:
    same_kind = [f for f in facts if f.kind == claim.kind]
    if not same_kind:
        return Result(claim, "UNSUPPORTED", notes=[f"No {claim.kind} facts are on file for this post."])

    scored = sorted(((keyword_score(f, claim.context), f) for f in same_kind), key=lambda x: -x[0])
    best = scored[0][0]

    if best == 0:
        # The wording doesn't point to any fact. If the number happens to equal a fact,
        # that's a lead worth a second look, not proof.
        hits = [f for f in same_kind if compare(claim, f)[0] == "SUPPORTED"]
        if hits:
            return Result(
                claim, "NEEDS_REVIEW",
                notes=[f"The number matches {', '.join(h.id for h in hits)}, but the wording doesn't tie it to that fact."],
                candidates=[f.id for f in same_kind],
            )
        return Result(claim, "UNSUPPORTED", notes=["No fact on file covers this number. It may be a typo or an invented figure."])

    top = [f for s, f in scored if s == best]
    if len(top) > 1:
        return Result(
            claim, "NEEDS_REVIEW",
            notes=[f"Wording fits {len(top)} facts equally: {', '.join(f.id for f in top)}."],
            candidates=[f.id for f in top],
        )
    return verify(claim, top[0], matched_by="rules")


def verify(claim: Claim, fact: Fact, matched_by: str) -> Result:
    status, note = compare(claim, fact)
    return Result(claim, status, fact=fact, notes=[note] if note else [], matched_by=matched_by)


def apply_attribution(result: Result, draft: Draft) -> Result:
    """Catch the 'we' problem: the publisher claiming a featured nonprofit's results as its own."""
    fact = result.fact
    if not fact or fact.type != "achievement" or fact.org_id == draft.voice:
        return result
    if not FIRST_PERSON.search(result.claim.context):
        return result
    note = (f"First-person wording makes the publisher ({draft.voice}) sound like it achieved this. "
            f"This result belongs to {fact.org_name}; name them as the one who did it.")
    if result.status in ("SUPPORTED", "WARNING"):
        result.status = "ATTRIBUTION"
    result.notes.append(note)
    return result
