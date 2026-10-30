# claimcheck

A command-line tool that checks the numbers in nonprofit campaign copy against each nonprofit's verified fact sheet before the copy is published. It reports each number as supported, wrong, or untraceable, and it flags posts where the publisher's "we" claims a nonprofit's results as its own.

Built for the MiraFlores AI case study. The written explanation is in `WRITEUP.md`.

## Live demo

**[LIVE URL GOES HERE]**

The web app (`streamlit_app.py`) runs the same `claimcheck` package as the command line. It adds no checking logic of its own. Pick a sample draft or edit the text, choose fact sheets, and click **Run check**. Every demo case below is available from the sample menu, including the invalid inputs.

Run the web app locally:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The web app was added after the original submission, at the reviewers' request for a hosted link. Its time is logged separately under "Time spent".

## Requirements

- Python 3.10 or newer
- The command-line tool uses only the standard library, with no packages to install. The web app needs Streamlit (`requirements.txt`).
- No API key needed for the demo. The optional live model step uses the Anthropic API if `ANTHROPIC_API_KEY` is set.

## Quick start

```bash
cd MiraFlores
./run_demo.sh                                  # runs all six demo cases
python3 -m unittest discover -s tests -v       # 24 tests
```

On Windows, run the commands inside `run_demo.sh` one at a time, or use Git Bash.

## Usage

```bash
python3 -m claimcheck DRAFT.md --facts ORG.json [--facts OTHER_ORG.json] \
    [--llm off|mock|anthropic] [--fixtures replies.json] [--out report.md] [--json report.json]
```

| Exit code | Meaning |
|---|---|
| 0 | Ready to publish (no blocking issues) |
| 1 | Blocked, with a fix list |
| 2 | Bad input; nothing was checked |

### Model modes

| `--llm` | What happens to ambiguous claims |
|---|---|
| `off` (default) | They stay `NEEDS_REVIEW` for a person |
| `mock` | Recorded replies from `--fixtures` are replayed. Labeled MOCKED in the report |
| `anthropic` | A live call to Claude (model set by `CLAIMCHECK_MODEL`, default `claude-haiku-5-5`). Any failure falls back to `NEEDS_REVIEW` |

## How it works

```
draft.md + fact sheets
   │
   ├─ 1. loader.py   validate inputs (every fact must have a source; the featured org's sheet must be loaded)
   ├─ 2. extract.py  find every number with regex: value, kind, qualifier ("more than", "nearly"), clause
   ├─ 3. match.py    pick the fact by keyword overlap in the clause → check the number with arithmetic
   ├─ 4. llm.py      only for ambiguous claims: the model picks WHICH fact (never a number); reply is validated
   ├─ 5. match.py    attribution check: first-person wording on another org's achievement
   └─ 6. report.py   Markdown fix list + JSON, verdict READY or BLOCKED
```

The model never produces or judges a number. Code does all the arithmetic, so a model mistake can at worst send a claim to a person for review.

### Statuses

| Status | Blocks publishing? | Meaning |
|---|---|---|
| SUPPORTED | No | Number agrees with a sourced fact |
| WARNING | No | Agrees, but worth a glance (dropped "more than", or the model chose the fact) |
| MISMATCH | Yes | Number disagrees with the fact it refers to |
| UNSUPPORTED | Yes | No fact on file covers this number |
| ATTRIBUTION | Yes | Publisher's "we" claims the featured nonprofit's result |
| NEEDS_REVIEW | Yes | Can't tell which fact this refers to |

### Qualifier rules

| Draft says | Passes when the source value F and claim C satisfy |
|---|---|
| `450` | C = F exactly. Rounding is allowed only when written rounded (`$2.3 million`, `25K`) |
| `more than 450`, `450+`, `over` | F ≥ C |
| `about 90%` | within 5% of F |
| `nearly 40` | F ≤ C and C − F ≤ 10% of C |
| Source itself says "more than F" | Claims up to F pass. Claims above F fail, since the source can't support them |

## Input formats

**Draft:** Markdown with front matter naming who publishes it and who it features.

```markdown
---
title: Nonprofit Spotlight
voice: harbor-city-gives          # org id of the publisher
featured_org: harbor-pathways     # org id the post is about
---
Since 2023, Harbor Pathways has placed more than 450 young adults in jobs.
```

**Fact sheet:** JSON, one per organization.

```json
{
  "org_id": "harbor-pathways",
  "org_name": "Harbor Pathways",
  "facts": [{
    "id": "f1",
    "statement": "Harbor Pathways has placed more than 450 young adults in jobs since 2023.",
    "value": 450, "kind": "count", "comparator": "at_least", "type": "achievement",
    "keywords": ["placed", "hired", "young adult"],
    "source": "2025 Impact Report, p. 2"
  }]
}
```

`kind`: money, count, percent. `comparator`: exact (default) or at_least. `type`: achievement (past result; triggers the attribution check), goal, context. `source` is required.

## Sample data and expected outputs

All sample data is synthetic. Harbor Pathways, Harbor City Gives and the Seabright Foundation are fictional, and every figure is invented.

| # | Command input | Expected result | Saved output |
|---|---|---|---|
| 1 | `samples/drafts/spotlight_draft.md` (an AI first draft) | BLOCKED, 3 issues: "more than 500" should be 450 and is written as "we" (attribution); "$250,000" should be $25,000; "$2,500" has no source. 6 supported, 1 model-matched warning | `samples/expected/1_spotlight_draft.md`, `.json` |
| 2 | `samples/drafts/spotlight_fixed.md` | READY, 8 supported, 1 warning | `samples/expected/2_spotlight_fixed.md` |
| 3 | `samples/drafts/org_own_post.md` (difficult case) | BLOCKED, 1 issue. The mocked model reply names a fact that doesn't exist, so it is rejected and "38" stays NEEDS_REVIEW. Also shows that an org may say "we" about its own results | `samples/expected/3_org_own_post.md` |
| 4 | draft + only `harbor_city_gives.json` | INPUT ERROR: the featured org's sheet isn't loaded | (stderr) |
| 5 | `samples/invalid/fact_missing_source.json` | INPUT ERROR: fact has no source | (stderr) |
| 6 | `samples/invalid/no_front_matter.md` | INPUT ERROR: missing voice/featured_org | (stderr) |

Excerpt from case 1:

```
## Verdict: BLOCKED (3 issues)

| C3 | 10 | more than 500 | FIX MISMATCH    | harbor-pathways:f1 | Source only supports more than 450. First-person wording makes the publisher ... |
| C5 | 14 | $250,000      | FIX MISMATCH    | harbor-pathways:f4 | Source says $25,000. |
| C8 | 18 | $2,500        | FIX UNSUPPORTED | none               | No fact on file covers this number. It may be a typo or an invented figure. |
```

## Implemented, mocked, deferred

**Implemented:** input validation, number extraction (money, counts, percents, K/million, qualifiers, clause context), keyword-based fact matching, arithmetic verification with qualifier rules, attribution check, model guardrails, Markdown and JSON reports, exit codes, tests.

**Mocked:** model replies in the demo (`samples/llm_fixtures.json`). The live Anthropic path is written and fails safely, but the demo doesn't depend on it. All data is synthetic.

**Deferred:**
- Spelled-out numbers ("ten young adults")
- Claims without numbers ("we train carpenters"); attribution only checks sentences with a number
- Years as claims ("since 2023"); years are skipped
- Reading facts straight from PDFs (fact sheets are hand-made JSON today)
- A reviewer override that records "I checked this, publish anyway"
- Keyword scoring is a plain count, so overly broad keywords can pull a claim to the wrong fact

## Time spent

Time Spent: 2 hrs and 35 mins. 

Web app added afterward at the reviewers' request: [FILL IN] mins.

## AI use

See the "How I used AI" section of `WRITEUP.md`.

## Project layout

```
claimcheck/       source (models, loader, extract, match, llm, pipeline, report, CLI)
tests/            unittest suite
samples/facts     synthetic fact sheets
samples/drafts    demo drafts
samples/invalid   bad inputs for error handling
samples/expected  saved reports from run_demo.sh
run_demo.sh       runs every case
WRITEUP.md        written submission (up to 4 pages)
```
