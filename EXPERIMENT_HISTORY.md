# C-01 supporting experiment history

This audit record preserves development and collection history separately from the final protocol described in the paper. It is included in the prepared anonymous source/evidence archives; no supplementary upload or public hosting is assumed. Original native data and frozen code are unchanged.

## Reporting population

Only `20261115-c01-main-02` contributes to the paper's experiment table: 18 planned, started, completed and valid trials; zero invalid or missing. The six schedule/lifetime cells have three repetitions each. Order is shuffled with seed 20261115 and fixed before execution; source, protocol, observer amendment and analysis hashes are bound by PREMAIN_FREEZE_R2 and run FREEZE records.

## Separate preliminary and interrupted runs

| Run | Planned | Started | Completed valid | Invalid/incomplete | Unstarted | Reporting role |
|---|---:|---:|---:|---:|---:|---|
| 20261115-c01-pilot-01 | 6 | 6 | 6 | 0 | 0 | Initial instrumentation validation; not pooled |
| 20261115-c01-main-01 | 18 | 6 | 5 | 1 | 12 | Interrupted collection; not pooled |
| 20261115-c01-pilot-02 | 6 | 6 | 6 | 0 | 0 | Revised-observer validation; not pooled |
| 20261115-c01-main-02 | 18 | 18 | 18 | 0 | 0 | Reported campaign |

The first main collection stopped under its frozen rule when the observer listed a normal-control target and then received 404 while inspecting it. Native removal had already completed, followed by SDK DELETE 204/destroy return. The affected record remains invalid for that collection; the other five valid records and 12 unstarted trials remain visible. This was an observation race, not evidence that native deletion failed.

The observer amendment uses raw exact-label summaries and explicit inspection. A404 is confirmed as disappearance only through a fresh empty exact-label read-back; still-listed/replaced identities or failed read-backs remain uncertain/error and halt admission. Thirteen CPU/local-HTTP checks passed, followed by a new full six-cell pilot and the separately frozen final 18-trial collection. SDK, proxy fault, lifetime settings, quotas, schedule definitions, observation horizons and shuffle seed were unchanged. No old observations were replaced or pooled into the final campaign.

A separate initial offline-analysis selector counted telemetry POST releases as create replies. The correction limits lifecycle create selectors to POST /sandboxes; original analysis and corrected output are retained. Native requests, events and outcomes were not rewritten. The final analysis was frozen before the reported campaign.

## Records in this package

- `raw/runs/<run-id>/`: complete HTTP requests/responses, native/driver events, observations, result/cleanup records and freezes for every attempt.
- `raw/code/c01-lost-reply/`: final protocol, observer amendment, prospective analysis plan, seeded freezes, execution and analysis code.
- `raw/revisions/observer-r2/`: source snapshot before the observer correction.
- `raw/reviews/`: source/protocol/implementation/pilot/final artifact audits and selector-correction records, all identified as internal model checks.
- `main02-analysis.json`: main-only aggregate and trial-level interpretation.

The standalone local study preserves the original unsanitized records. The prepared anonymous copy documents path-only sanitization with original/released hashes. Both preliminary pilots and the interrupted collection are excluded from the reported 18; their failed, invalid and unstarted accounting remains available here. This is supporting audit history, not evidence of public reviewer access or human source verification.
