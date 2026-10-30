"""Find every number in the draft that a donor would read as a factual claim.

This step is pure rules (regex). No model is involved, so the same draft always
produces the same claims, and a number can never be invented or dropped silently.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import Claim, Draft

NUMBER_RE = re.compile(
    r"""
    (?P<cur>\$)?
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    (?P<suffix>\s?(?:million|billion|thousand)\b|[kKmMbB]\b)?
    (?P<plus>\+)?
    (?P<pct>\s?(?:%|percent\b))?
    """,
    re.VERBOSE,
)

MULTIPLIERS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}

# Words just before a number that change what it claims. Checked longest first.
QUALIFIERS: List[Tuple[str, str]] = [
    ("more than", "at_least"), ("upwards of", "at_least"), ("at least", "at_least"), ("over", "at_least"),
    ("approximately", "approx"), ("roughly", "approx"), ("around", "approx"), ("about", "approx"), ("~", "approx"),
    ("nearly", "nearly"), ("almost", "nearly"), ("close to", "nearly"),
]

# Clause breaks: ; : and commas, but not the commas inside "2,342,349".
CLAUSE_BREAK = re.compile(r",(?!\d)|(?<!\d),|[;:]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
MARKDOWN_NOISE = re.compile(r"^\s*(#+|[-*>]|\d+\.)\s+")


def _clean(line: str) -> str:
    line = MARKDOWN_NOISE.sub("", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)  # [text](url) -> text
    return line.replace("**", "").replace("__", "").strip()


def sentences(draft: Draft):
    """Yield (line_number, sentence) for every sentence in the body."""
    for offset, raw in enumerate(draft.lines):
        text = _clean(raw)
        if not text:
            continue
        for s in SENTENCE_SPLIT.split(text):
            if s.strip():
                yield draft.body_start_line + offset, s.strip()


def _is_noise(sentence: str, m: re.Match) -> bool:
    """Numbers that are not claims: years, ordinals, dates, times, list markers."""
    num = m.group("num")
    after = sentence[m.end():m.end() + 2]
    before = sentence[max(0, m.start() - 1):m.start()]
    plain = not (m.group("cur") or m.group("suffix") or m.group("pct") or m.group("plus"))
    if plain and re.fullmatch(r"(19|20)\d\d", num):
        return True                                   # "since 2023", "Giving Day 2026"
    if re.match(r"(st|nd|rd|th)\b", sentence[m.end():m.end() + 3]):
        return True                                   # "6th year"
    if after[:1] in {"/", ":"} or before in {"/", ":"}:
        return True                                   # "9/30", "5:00"
    return False


def _clause(sentence: str, start: int, end: int) -> str:
    """The stretch of text between the clause breaks on either side of a number."""
    left, right = 0, len(sentence)
    for b in CLAUSE_BREAK.finditer(sentence):
        if b.end() <= start:
            left = b.end()
        elif b.start() >= end:
            right = b.start()
            break
    return sentence[left:right].strip()


def _qualifier(prefix: str, plus: bool) -> Tuple[str, str]:
    if plus:
        return "at_least", ""
    tail = prefix.lower().rstrip()
    for phrase, q in QUALIFIERS:
        start = len(tail) - len(phrase)
        # whole-word match only, so "takeover 5" is not read as "over 5"
        if tail.endswith(phrase) and (start == 0 or not tail[start - 1].isalpha()):
            return q, phrase
    return "exact", ""


def _precision(digits: str, suffix: str) -> float:
    """Rounding is only allowed when the writer visibly rounded ("2.3 million", "25K").
    A plain "450" against a source of 452 must match exactly, so precision is 0."""
    if not suffix and "." not in digits:
        return 0.0
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    return MULTIPLIERS.get(suffix, 1.0) * 10 ** -decimals


def extract_claims(draft: Draft) -> List[Claim]:
    claims: List[Claim] = []
    for line_no, sent in sentences(draft):
        for m in NUMBER_RE.finditer(sent):
            if _is_noise(sent, m):
                continue
            digits = m.group("num")
            value = float(digits.replace(",", ""))
            suffix = (m.group("suffix") or "").strip().lower()
            if suffix:
                value *= MULTIPLIERS[suffix]

            after = sent[m.end():m.end() + 9].lower()
            if m.group("pct"):
                kind = "percent"
            elif m.group("cur") or after.strip().startswith("dollars"):
                kind = "money"
            else:
                kind = "count"

            qualifier, phrase = _qualifier(sent[:m.start()], bool(m.group("plus")))
            literal = (phrase + " " if phrase else "") + m.group(0).strip()
            claims.append(Claim(
                id=f"C{len(claims) + 1}",
                literal=literal,
                value=value,
                kind=kind,
                qualifier=qualifier,
                precision=_precision(digits, suffix),
                sentence=sent,
                context=_clause(sent, m.start(), m.end()),
                line=line_no,
            ))
    return claims
