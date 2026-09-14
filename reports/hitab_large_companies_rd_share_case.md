# HiTab smoke test: large-company share of total R&D

## Input

- Example ID: `02cb638212c0f01dc6f041b0ac42009a`
- Question: “how many percentage points of total r&d did large companies
  (those with 250 or more employees) account for?”
- Gold: `0.876264` (ratio representation)
- Gold formula: `(I15 + I16 + I17 + I18 + I19 + I20) / I5`
- Required operations: `sum`, then `divide`

The hierarchy contains six leaf groups under `large companies`: 250–499,
500–999, 1,000–4,999, 5,000–9,999, 10,000–24,999, and 25,000 or more.
Their 2015 values sum to 311,793; the all-company total is 355,821.
Therefore, `311793 / 355821 = 0.8762636269`, or `87.62636269%`.

## Observed run

- Provider/model: Gemini / `gemini-3.6-flash`
- Configuration: Numerical IR, three candidate paths, temperature 0
- Online KG: 204 nodes, 192 edges, eight year-specific relations
- Best path: `path_2`
- Executed answer: `87.62636269360156%`
- LLM calls: 6
- Wall time: 78.284 seconds
- Strict benchmark-scale denotation: 0
- Ratio/percentage-normalized denotation: 1

The winning path used an algebraically equivalent complement strategy: it
retrieved the all-company total and the five groups below 250 employees,
computed their percentage of the total, and subtracted it from 100. Its output
is equivalent to the annotated direct sum of the six large-company leaves.

Two other candidate programs failed JSON/IR parsing. This case therefore
supports reporting execution success separately from final denotation and
supports retaining strict and scale-normalized metrics side by side.

## Provider observations

- Groq was tried first but exceeded its daily token quota.
- OpenRouter/free returned empty planner responses after JSON retry.
- Gemini 2.5 Flash was unavailable for the configured account.
- Gemini 3.6 Flash completed the run.
- NVIDIA NIM was deliberately excluded from the final retry policy.

These are operational observations from one smoke test, not benchmark-level
provider comparisons.
