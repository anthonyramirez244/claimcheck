"""Run with:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from claimcheck.extract import extract_claims  # noqa: E402
from claimcheck.llm import Resolver, validate_response  # noqa: E402
from claimcheck.match import compare  # noqa: E402
from claimcheck.models import Draft, Fact, InputError  # noqa: E402
from claimcheck.pipeline import run  # noqa: E402

S = lambda *p: os.path.join(ROOT, "samples", *p)  # noqa: E731
FACTS = [S("facts", "harbor_pathways.json"), S("facts", "harbor_city_gives.json")]
MOCK = Resolver("mock", S("llm_fixtures.json"))


def draft_of(text: str) -> Draft:
    return Draft(path="t.md", title="t", voice="a", featured_org="b", lines=text.splitlines(), body_start_line=1)


def fact(value, kind="count", comparator="exact"):
    return Fact(id="x:f1", org_id="x", org_name="X", statement="", value=value, kind=kind,
                comparator=comparator, type="achievement", keywords=[], source="s")


class ExtractTests(unittest.TestCase):
    def one(self, text):
        claims = extract_claims(draft_of(text))
        self.assertEqual(len(claims), 1, claims)
        return claims[0]

    def test_money_with_multiplier(self):
        c = self.one("We raised $2.3 million.")
        self.assertEqual((c.value, c.kind, c.precision), (2_300_000, "money", 100_000))

    def test_k_suffix_and_commas(self):
        self.assertEqual(self.one("A $25K goal.").value, 25_000)
        self.assertEqual(self.one("A $2,342,349 total.").value, 2_342_349)

    def test_qualifiers(self):
        self.assertEqual(self.one("more than 450 people").qualifier, "at_least")
        self.assertEqual(self.one("450+ people").qualifier, "at_least")
        self.assertEqual(self.one("nearly 40 employers").qualifier, "nearly")
        self.assertEqual(self.one("about 90% stay").qualifier, "approx")
        self.assertEqual(self.one("a takeover 5 times").qualifier, "exact")  # whole words only

    def test_percent(self):
        self.assertEqual(self.one("92% were employed").kind, "percent")

    def test_skips_years_ordinals_dates(self):
        self.assertEqual(extract_claims(draft_of("Since 2023, in our 6th year, on 9/30 at 5:00.")), [])

    def test_clause_context_is_separate(self):
        claims = extract_claims(draft_of("We placed 450 people, and our alumni network has grown to 38."))
        self.assertNotIn("alumni", claims[0].context)
        self.assertIn("alumni", claims[1].context)


class CompareTests(unittest.TestCase):
    def check(self, text, f):
        return compare(extract_claims(draft_of(text))[0], f)[0]

    def test_exact(self):
        self.assertEqual(self.check("450 people", fact(450)), "SUPPORTED")
        self.assertEqual(self.check("452 people", fact(450)), "MISMATCH")

    def test_rounding_only_when_written_rounded(self):
        self.assertEqual(self.check("$2.3 million", fact(2_342_349, "money")), "SUPPORTED")
        self.assertEqual(self.check("$2.5 million", fact(2_342_349, "money")), "MISMATCH")
        self.assertEqual(self.check("10 people", fact(12)), "MISMATCH")

    def test_more_than(self):
        self.assertEqual(self.check("more than 450", fact(452)), "SUPPORTED")
        self.assertEqual(self.check("more than 500", fact(452)), "MISMATCH")

    def test_nearly_must_be_slightly_above(self):
        self.assertEqual(self.check("nearly 40", fact(38)), "SUPPORTED")
        self.assertEqual(self.check("nearly 40", fact(41)), "MISMATCH")
        self.assertEqual(self.check("nearly 50", fact(38)), "MISMATCH")

    def test_source_only_says_more_than(self):
        f = fact(450, comparator="at_least")
        self.assertEqual(self.check("more than 450", f), "SUPPORTED")
        self.assertEqual(self.check("450 people", f), "WARNING")
        self.assertEqual(self.check("500 people", f), "MISMATCH")


class ModelGuardTests(unittest.TestCase):
    def test_rejects_unknown_id(self):
        self.assertIsNone(validate_response('{"fact_id": "x:f9"}', ["x:f1"])[0])

    def test_rejects_non_json(self):
        self.assertIsNone(validate_response("I think it's the first one.", ["x:f1"])[0])

    def test_accepts_listed_id_inside_chatter(self):
        self.assertEqual(validate_response('Sure: {"fact_id": "x:f1", "reason": "r"}', ["x:f1"])[0], "x:f1")

    def test_null_means_no_match(self):
        self.assertIsNone(validate_response('{"fact_id": null}', ["x:f1"])[0])


class PipelineTests(unittest.TestCase):
    def statuses(self, draft, resolver=MOCK):
        rep = run(S("drafts", draft), FACTS, resolver)
        return rep, {r.claim.literal + "@" + str(r.claim.line): r.status for r in rep.results}

    def test_first_draft_is_blocked_for_the_right_reasons(self):
        rep, st = self.statuses("spotlight_draft.md")
        self.assertFalse(rep.ready)
        self.assertEqual(st["more than 500@10"], "MISMATCH")
        self.assertEqual(st["$250,000@14"], "MISMATCH")
        self.assertEqual(st["$2,500@18"], "UNSUPPORTED")
        self.assertEqual(st["over $2.3 million@8"], "SUPPORTED")
        self.assertEqual(st["nearly 40@16"], "SUPPORTED")
        self.assertEqual(st["10@20"], "WARNING")  # model chose the fact, code checked the number
        c3 = next(r for r in rep.results if r.claim.line == 10)
        self.assertTrue(any("belongs to Harbor Pathways" in n for n in c3.notes))

    def test_fixed_draft_is_ready(self):
        rep, _ = self.statuses("spotlight_fixed.md")
        self.assertTrue(rep.ready)

    def test_attribution_flags_publisher_claiming_nonprofit_result(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("---\nvoice: harbor-city-gives\nfeatured_org: harbor-pathways\n---\n"
                     "Since 2023, we've placed more than 450 young adults in jobs.\n")
        rep = run(fh.name, FACTS, Resolver("off"))
        self.assertEqual(rep.results[0].status, "ATTRIBUTION")

    def test_org_writing_about_itself_may_say_we(self):
        rep, st = self.statuses("org_own_post.md")
        self.assertEqual(st["more than 450@6"], "SUPPORTED")

    def test_bad_model_answer_is_ignored(self):
        rep, st = self.statuses("org_own_post.md")
        self.assertEqual(st["38@6"], "NEEDS_REVIEW")
        self.assertFalse(rep.ready)

    def test_off_mode_leaves_ambiguity_for_a_person(self):
        _, st = self.statuses("spotlight_fixed.md", Resolver("off"))
        self.assertEqual(st["10@18"], "NEEDS_REVIEW")


class InvalidInputTests(unittest.TestCase):
    def test_wrong_fact_sheet(self):
        with self.assertRaises(InputError):
            run(S("drafts", "spotlight_draft.md"), [S("facts", "harbor_city_gives.json")], Resolver("off"))

    def test_fact_without_source(self):
        with self.assertRaises(InputError):
            run(S("drafts", "spotlight_draft.md"), [S("invalid", "fact_missing_source.json")], Resolver("off"))

    def test_missing_front_matter(self):
        with self.assertRaises(InputError):
            run(S("invalid", "no_front_matter.md"), FACTS, Resolver("off"))


if __name__ == "__main__":
    unittest.main()
