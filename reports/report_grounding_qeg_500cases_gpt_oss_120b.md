# QEG evidence-grounding report

A grounded answer has a final answer and an `EVIDENCE_PATH` containing at least one visible KG edge ID with no invalid citation. This measures citation/path validity, not whether the cited evidence entails the gold answer.

| Metric | Value |
| --- | ---: |
| Examples | 500 |
| EM | 61.20% |
| Token F1 | 69.29% |
| Answered | 431 |
| Grounded answers | 431 |
| Grounded rate among answers | 100.00% |
| End-to-end grounded answer rate | 86.20% |
| EM among grounded answers | 71.00% |
| L1 final answers / grounded paths | 380 / 379 |
| L2 final answers / grounded paths | 76 / 52 |
| CITE_EVIDENCE attempted / grounded / retried | 0 / 0 / 0 |
| Invalid citations | 25 |
| Contract rejections | 24 |

## Paired EM against baseline

| Metric | Value |
| --- | ---: |
| Shared examples | 500 |
| QEG correct, baseline wrong | 48 |
| Baseline correct, QEG wrong | 69 |
| Paired EM delta | -4.20% |
| Exact two-sided McNemar p | 0.06399591 |
