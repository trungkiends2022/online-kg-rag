# Reproducible benchmark subsets

This directory contains small, version-controlled evaluation subsets. Raw
datasets remain under `data/` and are intentionally ignored by Git.

## Python for benchmark commands

Set a known-good interpreter once in the terminal. The direct commands below use
this variable; the two HybridQA runner scripts perform the same import check and
automatically fall back from a broken `.venv` to `python3`.

```bash
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import src.run_baselines'
```

To use a different environment explicitly, set `PYTHON_BIN=/path/to/python`.

## FinQA

The `finqa/` subsets are sampled from the official FinQA development split with
seed `2027`. Sampling approximates the full split's marginal distributions for:

- final numerical operator;
- gold-evidence modality (`table_only`, `text_only`, or `both`);
- gold-program length (`1`, `2`, or `3+` operations).

Every final-operator category present in the development split is represented
when the requested sample size permits. Each `.distribution.json` file records
the source split, seed, distributions, and selected example IDs.

Regenerate the checked-in pilot subsets:

```bash
"$PYTHON_BIN" -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-balanced-20-seed2027.json \
  --report benchmarks/finqa/finqa-dev-balanced-20-seed2027.distribution.json \
  --size 20 --seed 2027

"$PYTHON_BIN" -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-balanced-50-seed2027.json \
  --report benchmarks/finqa/finqa-dev-balanced-50-seed2027.distribution.json \
  --size 50 --seed 2027

"$PYTHON_BIN" -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --report benchmarks/finqa/finqa-dev-balanced-100-seed2027.distribution.json \
  --size 100 --seed 2027
```

The focused 30-example subset contains exactly two gold arithmetic operations
per question and only uses the four well-supported primitive operators
`add`, `subtract`, `multiply`, and `divide`. Regenerate it with:

```bash
"$PYTHON_BIN" -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-2step-core-30-seed2027.json \
  --report benchmarks/finqa/finqa-dev-2step-core-30-seed2027.distribution.json \
  --size 30 --seed 2027 --exact-steps 2 --core-arithmetic-only
```

Run this focused subset with Numerical IR:

```bash
LLM_PROVIDER=openai_compatible "$PYTHON_BIN" -m src.run_baselines \
  --dataset finqa \
  --method numerical_ir \
  --input benchmarks/finqa/finqa-dev-2step-core-30-seed2027.json \
  --output data/results/finqa-dev-2step-core-30-numerical-ir.jsonl \
  --top-k 5 --n-paths 3 --max-replans 1 \
  --max-output-tokens 2048 --temperature 0 \
  --finqa-table-format official --resume
```

Run the 100-example Numerical IR benchmark with an OpenAI-compatible internal
model configured in `.env`:

```bash
LLM_PROVIDER=openai_compatible "$PYTHON_BIN" -m src.run_baselines \
  --dataset finqa \
  --method numerical_ir \
  --input benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --output data/results/finqa-dev-balanced-100-numerical-ir-internal.jsonl \
  --top-k 5 --n-paths 3 --max-replans 1 \
  --max-output-tokens 2048 --temperature 0 \
  --finqa-table-format official --resume
```

The 20/50/100-example subsets are intended for smoke testing and pilot evaluation.
Final paper results should use the full fixed development split after all
prompts and configurations have been frozen.

## Controlled FinQA 500

The following command produces five non-overlapping 100-example shards from
FinQA dev. Every gold program has one or two operations and only uses `add`,
`subtract`, `multiply`, or `divide`.

```bash
"$PYTHON_BIN" -m src.sample_finqa \
  --input data/FinQA/dataset/dev.json \
  --output benchmarks/finqa/finqa-dev-1to2step-core-100-seed2027.json \
  --size 100 --seed 2027 --min-steps 1 --max-steps 2 \
  --core-arithmetic-only --shards 5
```

Run shards sequentially by replacing `shard01` with `shard02` through `shard05`:

```bash
LLM_PROVIDER=openrouter "$PYTHON_BIN" -m src.run_baselines \
  --dataset finqa --method numerical_ir \
  --input benchmarks/finqa/finqa-dev-1to2step-core-100-seed2027-shard01.json \
  --output data/results/finqa-dev-1to2step-core-shard01.jsonl \
  --top-k 5 --n-paths 1 --max-replans 0 \
  --max-output-tokens 2048 --temperature 0 --finqa-table-format official \
  --llm-timeout-seconds 35 --llm-sdk-retries 0 --resume
```

## HybridQA table + text 100

This subset contains 100 dev examples with a verified table file, non-empty
linked passage file, answer, and unique table ID.

```bash
"$PYTHON_BIN" -m src.sample_hybridqa \
  --input data/HybridQA/released_data/dev.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output benchmarks/hybridqa/hybridqa-dev-table-text-100-seed2027.json \
  --size 100 --seed 2027
```

Run the HybridQA set with both table and linked-text sources:

```bash
LLM_PROVIDER=openrouter "$PYTHON_BIN" -m src.run_baselines \
  --dataset hybridqa --method online_kg \
  --input benchmarks/hybridqa/hybridqa-dev-table-text-100-seed2027.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-dev-table-text-100-online-kg.jsonl \
  --top-k 5 --second-stage-k 2 --n-paths 1 --max-replans 0 \
  --max-output-tokens 2048 --temperature 0 \
  --llm-timeout-seconds 35 --llm-sdk-retries 0 --resume
```

## HybridQA controlled 1,500

The 1,500-example split is sampled once from traced HybridQA dev records and
uses unique tables. Sampling and shard allocation are stratified by answer kind,
answer-node source, a table-to-text bridge proxy, and ordinal/superlative/count
cues. Each shard is shuffled deterministically. The result is seven balanced
200-example shards plus one proportionally balanced 100-example shard. Recreate
the master split and all eight shards with:

```bash
"$PYTHON_BIN" -m src.sample_hybridqa \
  --input data/HybridQA/released_data/dev.traced.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027.json \
  --size 1500 --shard-size 200 --seed 2027 --require-answer-node \
  --stratify-reasoning
```

Run all eight shards through the six controlled HybridQA methods. Each JSONL
also receives a `.jsonl.manifest.json` sidecar containing the model/provider,
code revision, input checksum, resource revisions, configuration, and a
fingerprint. `--resume` is allowed only when that fingerprint is identical;
use a new `RUN_TAG` after any model, prompt/code, data, or configuration change.

```bash
RUN_TAG=openrouter-deepseek-v4-flash-seed2027 \
scripts/run_hybridqa_1500.sh
```

Use the same `RUN_TAG` only to resume the exact same run. Without it, the
runner creates a UTC timestamped result directory. To run selected shards:

```bash
RUN_TAG=openrouter-deepseek-v4-flash-seed2027 \
scripts/run_hybridqa_1500.sh 01 02
```

This is a controlled, trace-eligible unique-table subset, not the complete
HybridQA development split; state that scope when reporting results.
