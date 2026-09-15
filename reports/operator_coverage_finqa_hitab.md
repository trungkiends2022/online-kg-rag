# Numerical operator coverage audit

Audit scope: official `train`, `dev`, and public `test` annotations stored
locally. FinQA private test is excluded because it has no released gold
programs. HiTab's duplicate `test_samples_qualitycheck.jsonl` is excluded.

## FinQA (8,281 examples)

| Gold operator | Occurrences | Numerical IR |
|---|---:|---|
| divide | 5,901 | `divide` |
| subtract | 3,676 | `subtract` |
| add | 1,952 | `add` |
| multiply | 759 | `multiply` |
| greater | 154 | `greater` |
| table_average | 129 | `table_average` |
| table_max | 66 | `table_max` |
| table_sum | 50 | `table_sum` |
| table_min | 36 | `table_min` |
| exp | 9 | `exp` |

All released FinQA gold operator types have a direct IR implementation.

## HiTab (10,672 examples)

| HiTab annotation | Occurrences | Numerical IR mapping |
|---|---:|---|
| none | 7,536 | `lookup` |
| pair-argmax | 703 | `argmax` over two label/value pairs |
| div | 582 | `divide` |
| argmax | 356 | `argmax` |
| opposite | 355 | `negate` |
| sum | 284 | `table_sum` / `add` |
| diff | 265 | `subtract` |
| pair-argmin | 219 | `argmin` over two pairs |
| argmin | 123 | `argmin` |
| max | 70 | `table_max` |
| topk-argmax | 68 | `topk_argmax` |
| greater_than | 61 | `greater` or `filter_greater` |
| min | 43 | `table_min` |
| average | 39 | `table_average` |
| less_than | 34 | `less` or `filter_less` |
| kth-argmax | 29 | `kth_argmax` |
| range | 19 | `range` returning `[maximum, minimum]` |
| counta | 14 | `count` (usually after filtering) |
| topk-argmin | 11 | `topk_argmin` |
| kth-argmin | 6 | `kth_argmin` |

All released HiTab aggregation labels now have an executable mapping. Coverage
of the operator vocabulary does not imply correct program generation: the
remaining challenges are selecting the complete label/value set, respecting
header hierarchy, choosing thresholds and $k$, ordering subtraction, and
normalizing units.
