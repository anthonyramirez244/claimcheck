# Claim check: Nonprofit Spotlight - Harbor Pathways (AI first draft)

- Draft: `samples/drafts/spotlight_draft.md`
- Publisher: `harbor-city-gives` | Featured nonprofit: `harbor-pathways`
- Fact sheets: Harbor City Gives, Harbor Pathways (8 facts)
- Model step: mock (recorded replies, not a live model)

## Verdict: BLOCKED (3 issues)

Claims found: 2 mismatch, 6 supported, 1 unsupported, 1 warning

| ID | Line | Claim | Status | Fact | Note |
|---|---|---|---|---|---|
| C1 | 8 | over $2.3 million | OK SUPPORTED | harbor-city-gives:f1 |  |
| C2 | 8 | 270 | OK SUPPORTED | harbor-city-gives:f2 |  |
| C3 | 10 | more than 500 | FIX MISMATCH | harbor-pathways:f1 | Source only supports more than 450. First-person wording makes the publisher (harbor-city-gives) sound like it achieved this. This result belongs to Harbor Pathways; name them as the one who did it. |
| C4 | 12 | 92% | OK SUPPORTED | harbor-pathways:f2 |  |
| C5 | 14 | $250,000 | FIX MISMATCH | harbor-pathways:f4 | Source says $25,000. |
| C6 | 14 | 10 | OK SUPPORTED | harbor-pathways:f5 |  |
| C7 | 16 | nearly 40 | OK SUPPORTED | harbor-pathways:f3 |  |
| C8 | 18 | $2,500 | FIX UNSUPPORTED | none | No fact on file covers this number. It may be a typo or an invented figure. |
| C9 | 20 | 10 | CHECK WARNING | harbor-pathways:f5 | Fact chosen by model (MOCKED: The 10 lives refers to the 10 young adults the campaign goal funds.) Number verified by code. Confirm the model picked the right fact. |
| C10 | 22 | $100,000 | OK SUPPORTED | harbor-city-gives:f3 |  |

## Fix before publishing

**C3 (line 10): MISMATCH**
> Since 2023, we've placed more than 500 young adults in careers with family-sustaining wages.
- Source only supports more than 450.
- First-person wording makes the publisher (harbor-city-gives) sound like it achieved this. This result belongs to Harbor Pathways; name them as the one who did it.
- Fact on file: Harbor Pathways has placed more than 450 young adults in jobs since 2023. (source: Harbor Pathways 2025 Impact Report, p. 2 (synthetic))

**C5 (line 14): MISMATCH**
> This Giving Day, Harbor Pathways is raising $250,000 to give 10 young adults a complete career pathway, including training, mentorship and job placement.
- Source says $25,000.
- Fact on file: 2026 Giving Day goal: $25,000. (source: Campaign profile submitted to Harbor City Gives, Aug 2026 (synthetic))

**C8 (line 18): UNSUPPORTED**
> Just $2,500 covers transportation for an entire cohort.
- No fact on file covers this number. It may be a typo or an invented figure.

## Worth a quick look (not blocking)

- C9 (line 20) "10": Fact chosen by model (MOCKED: The 10 lives refers to the 10 young adults the campaign goal funds.) Number verified by code. Confirm the model picked the right fact.

