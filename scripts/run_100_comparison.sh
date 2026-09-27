#!/usr/bin/env bash
set -e

PYTHON="/workspace/kiennt/online-kg-rag/.venv/bin/python"

echo "=== 1/3: Running OUEG (online_unified_evidence_graph) 100 cases ==="
$PYTHON -m src.run_baselines \
  --dataset hybridqa \
  --method online_unified_evidence_graph \
  --input benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard02.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-shard02-100cases-oueg-1024-20260928.jsonl \
  --limit 100 \
  --max-output-tokens 1024 \
  --max-workers 4 \
  --llm-max-concurrent-requests 4 \
  --resume

echo "=== 2/3: Running Direct LLM (direct_llm) 100 cases ==="
$PYTHON -m src.run_baselines \
  --dataset hybridqa \
  --method direct_llm \
  --input benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard02.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-shard02-100cases-direct-llm-1024-20260928.jsonl \
  --limit 100 \
  --max-output-tokens 1024 \
  --max-workers 4 \
  --llm-max-concurrent-requests 4 \
  --resume

echo "=== 3/3: Comparing OUEG vs Direct LLM with Ambiguity Evaluation ==="
$PYTHON scripts/compare_oueg_direct.py \
  --oueg data/results/hybridqa-shard02-100cases-oueg-1024-20260928.jsonl \
  --direct data/results/hybridqa-shard02-100cases-direct-llm-1024-20260928.jsonl \
  --markdown reports/benchmark_shard02_100cases_oueg_vs_direct_ambiguity.md

echo "=== Benchmark Pipeline Complete! ==="
