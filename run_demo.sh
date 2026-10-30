#!/usr/bin/env bash
# Runs every demo case and saves the reports to samples/expected/.
# No API key needed: the model step uses recorded (MOCKED) replies.
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
FACTS="--facts samples/facts/harbor_pathways.json --facts samples/facts/harbor_city_gives.json"
MOCK="--llm mock --fixtures samples/llm_fixtures.json"

run() { echo; echo "=================== $1"; shift; "$PY" -m claimcheck "$@"; echo "[exit code $?]"; }

run "1. Representative case: AI first draft (expect BLOCKED, exit 1)" \
    samples/drafts/spotlight_draft.md $FACTS $MOCK --out samples/expected/1_spotlight_draft.md --json samples/expected/1_spotlight_draft.json
run "2. Same post after fixes (expect READY, exit 0)" \
    samples/drafts/spotlight_fixed.md $FACTS $MOCK --out samples/expected/2_spotlight_fixed.md
run "3. Difficult case: model gives a bad answer (expect BLOCKED, exit 1)" \
    samples/drafts/org_own_post.md $FACTS $MOCK --out samples/expected/3_org_own_post.md
run "4. Invalid input: wrong org's fact sheet (expect INPUT ERROR, exit 2)" \
    samples/drafts/spotlight_draft.md --facts samples/facts/harbor_city_gives.json
run "5. Invalid input: fact with no source (expect INPUT ERROR, exit 2)" \
    samples/drafts/spotlight_draft.md --facts samples/invalid/fact_missing_source.json --facts samples/facts/harbor_city_gives.json
run "6. Invalid input: draft with no front matter (expect INPUT ERROR, exit 2)" \
    samples/invalid/no_front_matter.md $FACTS
