## How each step works

### 1. Draft
The campaign post being checked. Pick a sample or edit the text directly; every change is checked on the next run.

The front matter at the top names who publishes the post (`voice`) and which nonprofit it features (`featured_org`).

The checker finds every number in the draft, plus the words that change its meaning, such as "more than", "nearly" or "about". Years, dates and times are skipped.

### 2. Fact sheets
Each nonprofit's verified facts. Every fact has a value and a source a person can open.

**Keep the featured nonprofit's sheet checked.** The samples feature Harbor Pathways, so that sheet must be selected. Without it, the tool stops with an input error instead of checking against the wrong organization's facts.

Keywords on each fact decide which fact a number refers to. Code then checks the number with plain arithmetic.

The "Invalid" sheet has a fact with no source, to show how bad input is rejected.

### 3. Model step
Used only when the wording doesn't point to one fact, such as "That's 10 lives changed."

**Recorded replies (MOCKED):** replays saved model answers so the demo runs without an API key. One saved reply is deliberately bad, to show that it gets rejected.

**Off:** those claims stay "Needs review" for a person.

The model only picks which fact a sentence means. It never supplies a number, and code still checks the value. A model match is marked as a warning so a person takes a quick look.

### Results
- **Blocks publishing:** Mismatch, Unsupported, Attribution, Needs review
- **Does not block:** Supported, Warning

---

*All sample data is synthetic. Harbor Pathways, Harbor City Gives and the Seabright Foundation are fictional.*

*Built by Anthony Ramirez for the MiraFlores AI case study.*
