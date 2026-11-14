# OUEG full-read + focused semantic re-read: two-case micro-experiment

This deterministic harness validates control flow, provenance preservation, and
diagnostics; it is not an answer-quality benchmark of a live model.

## Protocol

1. L1 receives the complete compact OUEG (`use_path_focused_prompt=False`).
2. For a structural `SCORE_COLLISION_TIE`, the simulated reader returns
   `NEED_FOCUS` with two existing candidate names, `blocker_type`, and an exact
   `needed_check`.
3. When L1 reports `missing_link` or `insufficient_evidence`, L2 first adds
   only candidate-linked passages from the supplied corpus, with the same
   budget for every candidate. It rebuilds the complete OUEG and places the
   resulting grounded semantic delta in the attention-only handoff.
4. L2 receives a small state capsule, rather than assuming it remembers L1:
   original question, blocker, complete row bindings for focus candidates,
   candidate-linked evidence, and retrieval coverage. It does not receive
   scores or unrelated graph context.
5. `complete_re_read` remains an explicit diagnostic ablation; it is not the
   default L2 prompt.
6. L2 returns either a grounded final span or an `UNRESOLVED` diagnostic. No
   top-1 fallback is allowed.

### Diagnostic-grounded focus recovery

For an L1 `missing_link`/`insufficient_evidence` diagnostic, OUEG resolves
the named entity in `needed_check` against existing table values and row
bindings before retrieval. Rank, year, and other scalar anchors are not used
as entity queries. It then retrieves the focused row's links first and uses a
bounded lexical fallback over the supplied example passages. The small L2
capsule also retains a bounded set of L1-visible witnesses matching
`needed_check`; this prevents a relevant passage already present in L1 from
being accidentally pruned away.

## Synthetic evidence

Both table rows have rate `21%`:

| Jurisdiction | Rate |
|---|---:|
| Alpha | 21% |
| Beta | 21% |

Question: `Which jurisdiction has a 21% rate and is named after a river?`

## Cases

| Case | Textual semantic evidence | L2 outcome | Expected system decision |
|---|---|---|---|
| Semantic resolution | Alpha is **not** named after a river; Beta is named after the Beta River | `FINAL_ANSWER: Beta` | `verified_after_focus` |
| Logical ambiguity | Alpha is named after the Alpha River; Beta is named after the Beta River | `UNRESOLVED: conflicting_evidence` | `grounded_abstention` |

## Result

Both cases passed in `tests/test_online_unified_evidence_graph.py` as
`test_oueg_two_case_focus_experiment`.

The experiment demonstrates that full OUEG L1 plus focused semantic L2 can
resolve a tie only when the text supplies a discriminating fact. When it does
not, the system reports the remaining blocker instead of converting uncertainty
into a guessed answer.

## Live GPT-OSS 120B check via OpenRouter

Run on 2026-10-25 with `LLM_PROVIDER=openrouter`,
`OPENROUTER_MODEL=openai/gpt-oss-120b`, reasoning enabled, temperature 0, and
`max_output_tokens=1024`. Only the synthetic two-case payload above was sent.

| Case | Calls | Model response / outcome |
|---|---:|---|
| Semantic resolution | 1 | `FINAL_ANSWER: Beta` |
| Missing-link augmentation | 2 | L1 emitted `UNRESOLVED` with `missing_link`: no evidence that either jurisdiction was named after a river. L2 added `/wiki/Alpha` and `/wiki/Beta` (one linked passage per candidate), rebuilt the OUEG to 30 records / 2 contexts, and returned `FINAL_ANSWER: Beta`. |

The previous logical-ambiguity live case remains the negative control: it
called L2 but added no evidence because its blocker was `candidate_collision`;
L2 correctly returned `UNRESOLVED` rather than guessing. The new runner
replaces that second live payload with the missing-link case so the added
retrieval branch itself is exercised.

At 512 output tokens, the reasoning-enabled model truncated the structured
diagnostic. The 1024-token budget completed both structured responses, so this
is the minimum budget used by the experiment runner for this model.

## Benchmark command

Run the full OUEG L1 + L2 augmentation branch on a HybridQA shard:

```bash
OPENROUTER_API_KEY=... \
bash scripts/run_hybridqa_oueg_focus_augmentation.sh --shard 02 --limit 100
```

The command uses full compact OUEG at L1, keeps both collision expansion and
the diagnostic-triggered L2 augmentation enabled, and uses the small
`delta_only` L2 capsule. It records the effective configuration in the output
manifest. Add `--no-collision-expansion` to isolate the incremental L2
augmentation effect, or `--l2-complete-re-read` for the old diagnostic
ablation.
