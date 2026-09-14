# Reproducible benchmark subsets

This directory contains small, version-controlled evaluation subsets. Raw
datasets remain under `data/` and are intentionally ignored by Git.

## FinQA

The `finqa/` subsets are sampled from the official FinQA development split with
seed `2027`. Sampling approximates the full split's marginal distributions for:

- final numerical operator;
- gold-evidence modality (`table_only`, `text_only`, or `both`);
- gold-program length (`1`, `2`, or `3+` operations).

Every final-operator category present in the development split is represented
when the requested sample size permits. Each `.distribution.json` file records
the source split, seed, distributions, and selected example IDs.

Regenerate both checked-in subsets:

```bash
.venv/bin/python -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-balanced-50-seed2027.json \
  --report benchmarks/finqa/finqa-dev-balanced-50-seed2027.distribution.json \
  --size 50 --seed 2027

.venv/bin/python -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --report benchmarks/finqa/finqa-dev-balanced-100-seed2027.distribution.json \
  --size 100 --seed 2027
```

Run the 100-example Numerical IR benchmark with an OpenAI-compatible internal
model configured in `.env`:

```bash
LLM_PROVIDER=openai_compatible .venv/bin/python -m src.run_baselines \
  --dataset finqa \
  --method numerical_ir \
  --input benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --output data/results/finqa-dev-balanced-100-numerical-ir-internal.jsonl \
  --top-k 5 --n-paths 3 --max-replans 1 \
  --max-output-tokens 2048 --temperature 0 \
  --finqa-table-format official --resume
```

The 50/100-example subsets are intended for smoke testing and pilot evaluation.
Final paper results should use the full fixed development split after all
prompts and configurations have been frozen.
