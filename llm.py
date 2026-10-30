"""Optional model step for claims the rules could not place.

The model gets one narrow job: given a sentence and a short list of candidate facts,
say WHICH fact (or none) the sentence refers to. It never supplies a number. Whatever
it answers is validated, and the number is then checked by code in match.verify().

Modes:
  off        no model; ambiguous claims stay NEEDS_REVIEW for a person (default)
  mock       replay recorded answers from a JSON file (labeled MOCKED in the report)
  anthropic  call the Claude API (needs ANTHROPIC_API_KEY; not required to run the demo)
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Dict, List, Optional, Tuple

from .models import Fact

DEFAULT_MODEL = os.environ.get("CLAIMCHECK_MODEL", "claude-haiku-5-5")

PROMPT = """You are helping a nonprofit staff member fact-check a donor-facing post.

Sentence from the draft:
"{sentence}"

The number being checked in that sentence: {literal}

Candidate facts from the nonprofit's verified fact sheet:
{facts}

Which single fact is this sentence's number referring to? If none of them clearly
describes the same thing, answer null. Do not judge whether the number is correct;
only identify the fact.

Reply with JSON only: {{"fact_id": "<id or null>", "reason": "<one short sentence>"}}"""


def sentence_key(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence.strip().lower())


def validate_response(raw: str, candidate_ids: List[str]) -> Tuple[Optional[str], str]:
    """Return (fact_id or None, explanation). Anything malformed is treated as no answer."""
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return None, "Model reply was not JSON; ignored."
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None, "Model reply was not valid JSON; ignored."
    fid = data.get("fact_id")
    reason = str(data.get("reason", "")).strip()
    if fid in (None, "null", ""):
        return None, f"Model found no matching fact. {reason}".strip()
    if fid not in candidate_ids:
        return None, f"Model picked '{fid}', which was not one of the candidates; ignored."
    return fid, reason


class Resolver:
    def __init__(self, mode: str = "off", fixtures_path: Optional[str] = None):
        if mode not in ("off", "mock", "anthropic"):
            raise ValueError(f"unknown llm mode: {mode}")
        self.mode = mode
        self.fixtures: Dict[str, str] = {}
        if mode == "mock":
            if not fixtures_path or not os.path.isfile(fixtures_path):
                raise ValueError("mock mode needs --fixtures pointing to a JSON file of recorded replies")
            with open(fixtures_path, encoding="utf-8") as fh:
                self.fixtures = {sentence_key(k): v for k, v in json.load(fh).items()}

    def resolve(self, sentence: str, literal: str, candidates: List[Fact]) -> Tuple[Optional[str], str]:
        if self.mode == "off":
            return None, "Model step is off; a person needs to confirm which fact this is."
        ids = [f.id for f in candidates]
        if self.mode == "mock":
            raw = self.fixtures.get(sentence_key(sentence))
            if raw is None:
                return None, "MOCKED: no recorded reply for this sentence."
            fid, why = validate_response(raw, ids)
            return fid, f"MOCKED: {why}"
        try:
            raw = self._call_anthropic(sentence, literal, candidates)
        except Exception as e:  # network, auth, rate limit: fail safe, keep it for a person
            return None, f"Model call failed ({type(e).__name__}); left for a person."
        return validate_response(raw, ids)

    def _call_anthropic(self, sentence: str, literal: str, candidates: List[Fact]) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        facts = "\n".join(f'- {f.id}: {f.statement}' for f in candidates)
        body = json.dumps({
            "model": DEFAULT_MODEL,
            "max_tokens": 200,
            "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT.format(sentence=sentence, literal=literal, facts=facts)}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return "".join(block.get("text", "") for block in data.get("content", []))
