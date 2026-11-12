# QEG evidence-grounding report

A grounded answer has a final answer and an `EVIDENCE_PATH` containing at least one visible KG edge ID with no invalid citation. This measures citation/path validity, not whether the cited evidence entails the gold answer.

| Metric | Value |
| --- | ---: |
| Examples | 200 |
| EM | 53.00% |
| Token F1 | 59.31% |
| Answered | 161 |
| Grounded answers | 155 |
| Grounded rate among answers | 96.27% |
| End-to-end grounded answer rate | 77.50% |
| EM among grounded answers | 64.52% |
| L1 final answers / grounded paths | 127 / 0 |
| L2 final answers / grounded paths | 34 / 0 |
| CITE_EVIDENCE attempted / grounded / retried | 0 / 0 / 0 |
| Invalid citations | 6 |
| Contract rejections | 0 |
