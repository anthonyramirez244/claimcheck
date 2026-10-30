"""The one core workflow: draft + fact sheets in, a publish/block decision out."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .extract import extract_claims
from .llm import Resolver
from .loader import load_inputs
from .match import apply_attribution, match_claim, verify
from .models import Draft, Fact, Result


@dataclass
class Report:
    draft: Draft
    facts: List[Fact]
    results: List[Result]
    llm_mode: str

    @property
    def blocking(self) -> List[Result]:
        return [r for r in self.results if r.blocking]

    @property
    def ready(self) -> bool:
        return not self.blocking


def run(draft_path: str, fact_paths: List[str], resolver: Resolver) -> Report:
    draft, facts = load_inputs(draft_path, fact_paths)
    by_id = {f.id: f for f in facts}
    results: List[Result] = []

    for claim in extract_claims(draft):
        result = match_claim(claim, facts)

        if result.status == "NEEDS_REVIEW":
            candidates = [by_id[i] for i in result.candidates]
            fact_id, why = resolver.resolve(claim.sentence, claim.literal, candidates)
            if fact_id:
                # The model only chose the fact. Code still checks the number.
                result = verify(claim, by_id[fact_id], matched_by="model")
                result.notes.insert(0, f"Fact chosen by model ({why})")
                if result.status == "SUPPORTED":
                    result.status = "WARNING"
                    result.notes.append("Number verified by code. Confirm the model picked the right fact.")
            else:
                result.notes.append(why)

        results.append(apply_attribution(result, draft))

    return Report(draft=draft, facts=facts, results=results, llm_mode=resolver.mode)
