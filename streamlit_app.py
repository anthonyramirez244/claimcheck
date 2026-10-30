"""Web front end for claimcheck.

All checking logic lives in the claimcheck package and is unchanged. This file only
collects inputs, calls claimcheck.pipeline.run(), and displays the result.

Run locally:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from claimcheck.llm import Resolver
from claimcheck.models import InputError
from claimcheck.pipeline import run
from claimcheck.report import to_json, to_markdown

ROOT = Path(__file__).parent
SAMPLES = ROOT / "samples"
FIXTURES = str(SAMPLES / "llm_fixtures.json")

DRAFTS = {
    "1. AI first draft (representative case)": SAMPLES / "drafts" / "spotlight_draft.md",
    "2. Same post after fixes": SAMPLES / "drafts" / "spotlight_fixed.md",
    "3. Nonprofit's own post, bad model reply (difficult case)": SAMPLES / "drafts" / "org_own_post.md",
    "4. Invalid: draft with no front matter": SAMPLES / "invalid" / "no_front_matter.md",
}
SHEETS = {
    "Harbor Pathways (featured nonprofit)": SAMPLES / "facts" / "harbor_pathways.json",
    "Harbor City Gives (campaign host)": SAMPLES / "facts" / "harbor_city_gives.json",
    "Invalid: Harbor Pathways sheet with a fact missing its source": SAMPLES / "invalid" / "fact_missing_source.json",
}
STATUS_HELP = {
    "SUPPORTED": "Matches a sourced fact",
    "WARNING": "Matches, but worth a glance",
    "MISMATCH": "Disagrees with the fact it refers to",
    "UNSUPPORTED": "No fact on file covers it",
    "ATTRIBUTION": "Publisher's 'we' claims the nonprofit's result",
    "NEEDS_REVIEW": "Can't tell which fact it refers to",
}

st.set_page_config(page_title="claimcheck", page_icon="✅", layout="wide")

# ---------- sidebar: what this is ----------
with st.sidebar:
    st.header("About")
    st.write(
        "Checks every number in nonprofit campaign copy against each nonprofit's verified "
        "fact sheet before it's published, and flags posts where the publisher's \"we\" "
        "takes credit for a nonprofit's results."
    )
    st.markdown(
        "**How it decides**\n"
        "1. Code finds every number and its qualifier (\"more than\", \"nearly\").\n"
        "2. Keywords in the same clause pick the fact it refers to.\n"
        "3. Code checks the number with plain arithmetic.\n"
        "4. Only when the wording is vague, a model picks which fact is meant. "
        "It never supplies a number, and code still checks the value."
    )
    st.caption(
        "All sample data is synthetic. Harbor Pathways, Harbor City Gives and the Seabright "
        "Foundation are fictional. The model step in this demo replays recorded replies (MOCKED)."
    )
    st.caption("Built by Anthony Ramirez for the MiraFlores AI case study.")

st.title("claimcheck")
st.write("Paste or pick a campaign draft, choose the fact sheets to check it against, then run the check.")

# ---------- inputs ----------
left, right = st.columns([3, 2])

with left:
    st.subheader("1. Draft")
    choice = st.selectbox("Start from a sample", list(DRAFTS), index=0)
    sample_text = DRAFTS[choice].read_text(encoding="utf-8")
    draft_text = st.text_area(
        "Draft text (edit freely; the front matter at the top says who publishes it and who it features)",
        value=sample_text,
        height=360,
        key=f"draft_{choice}",
    )

with right:
    st.subheader("2. Fact sheets")
    picked = []
    for i, name in enumerate(SHEETS):
        default = i < 2
        if st.checkbox(name, value=default, key=f"sheet_{i}"):
            picked.append(str(SHEETS[name]))
    uploaded = st.file_uploader("Or add your own fact sheet (JSON)", type=["json"], accept_multiple_files=True)

    with st.expander("View a fact sheet"):
        peek = st.selectbox("Sheet", list(SHEETS), label_visibility="collapsed")
        st.code(SHEETS[peek].read_text(encoding="utf-8"), language="json")

    st.subheader("3. Model step")
    mode_label = st.radio(
        "How to handle claims the rules can't place",
        ["Recorded replies (MOCKED)", "Off: leave them for a person"],
        index=0,
    )
    mode = "mock" if mode_label.startswith("Recorded") else "off"

run_it = st.button("Run check", type="primary", use_container_width=True)

# ---------- run ----------
if run_it:
    with tempfile.TemporaryDirectory() as tmp:
        draft_path = os.path.join(tmp, "draft.md")
        Path(draft_path).write_text(draft_text, encoding="utf-8")
        fact_paths = list(picked)
        for i, f in enumerate(uploaded or []):
            p = os.path.join(tmp, f"uploaded_{i}.json")
            Path(p).write_bytes(f.getvalue())
            fact_paths.append(p)

        if not fact_paths:
            st.error("INPUT ERROR: choose at least one fact sheet.")
            st.stop()

        try:
            rep = run(draft_path, fact_paths, Resolver(mode, FIXTURES if mode == "mock" else None))
        except InputError as e:
            st.error("INPUT ERROR: " + str(e).replace(draft_path, "Draft").replace(tmp + os.sep, ""))
            st.caption("Nothing was checked. Bad input stops the run instead of producing a misleading report.")
            st.stop()

        rep.draft.path = "pasted draft" if draft_text != sample_text else str(DRAFTS[choice].relative_to(ROOT))
        st.divider()
        if not rep.results:
            st.success("READY: no numeric claims found, so there was nothing to verify.")
        elif rep.ready:
            st.success(f"READY to publish. {len(rep.results)} claims checked, none blocking.")
        else:
            n = len(rep.blocking)
            st.error(f"BLOCKED: {n} issue{'s' if n != 1 else ''} to fix before publishing.")

        if rep.results:
            counts = {}
            for r in rep.results:
                counts[r.status] = counts.get(r.status, 0) + 1
            cols = st.columns(len(STATUS_HELP))
            for col, (status, helptext) in zip(cols, STATUS_HELP.items()):
                col.metric(status.replace("_", " ").title(), counts.get(status, 0), help=helptext)

            rows = [{
                "ID": r.claim.id,
                "Line": r.claim.line,
                "Claim": r.claim.literal,
                "Status": r.status,
                "Fact": r.fact.id if r.fact else ("; ".join(r.candidates) or "none"),
                "Matched by": r.matched_by,
                "Note": " ".join(r.notes),
            } for r in rep.results]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                         column_config={"Note": st.column_config.TextColumn(width="large")})

            if rep.blocking:
                st.subheader("Fix before publishing")
                for r in rep.blocking:
                    with st.container(border=True):
                        st.markdown(f"**{r.claim.id} (line {r.claim.line}): {r.status}**")
                        st.markdown(f"> {r.claim.sentence}")
                        for note in r.notes:
                            st.markdown(f"- {note}")
                        if r.fact:
                            st.caption(f"Fact on file: {r.fact.statement} (source: {r.fact.source})")

            warns = [r for r in rep.results if r.status == "WARNING"]
            if warns:
                st.subheader("Worth a quick look (not blocking)")
                for r in warns:
                    st.markdown(f"- **{r.claim.id}** (line {r.claim.line}) \"{r.claim.literal}\": {' '.join(r.notes)}")

        d1, d2 = st.columns(2)
        d1.download_button("Download report (Markdown)", to_markdown(rep), file_name="claimcheck_report.md")
        d2.download_button("Download report (JSON)", to_json(rep), file_name="claimcheck_report.json")
