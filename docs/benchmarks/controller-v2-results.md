# Controller Benchmark v2

Synthetic, approval-assisted controller evaluation. Not merchant or causal-lift evidence.

Coverage: 100 seeds per scenario, 30 virtual days, 1200 matched scenario/variant/arm rows.
Hard-policy violations: **0**. This gate alone is not release approval.
Non-timing evidence: `sha256:a1aeb60320deb3a202a6bc00ac1397f25a0d8b3a59bd2c74ecbe2cd321328e76`.
Source fingerprint: `sha256:9562893ef5a7fb686cefddd267d68a5aba832395428638ab8edd7b2f887aa5df`.

## Environment

```json
{
  "asyncpg": "0.30.0",
  "engine_version": "simulator.2",
  "platform": "macOS-14.6-arm64-arm-64bit",
  "postgresql": "16.15",
  "python": "3.12.11",
  "source_fingerprint": "sha256:9562893ef5a7fb686cefddd267d68a5aba832395428638ab8edd7b2f887aa5df",
  "sqlalchemy": "2.0.38"
}
```

## Results

All arms and variants are retained, including no-action and unfavorable outcomes.
Money and CAC use integer minor units; margin is a fraction. Missing CAC is counted.
Dispersion is population standard deviation; percentiles are linearly interpolated.

### acquisition_v1 / inventory_infeasible / goal_conditioned_controller

Objective: `new_customers` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 0; initial/final infeasibility: 100/100; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 5541.63 | 124.44457842750724 | 5384.6 | 5542.5 | 5682.0 |
| cac_minor | 100 | 0 | 134.92 | 3.051819129633996 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415317 | 0.007638010932173375 | 0.40669 | 0.41475 | 0.4252 |
| contribution_profit_minor | 100 | 0 | 49172232.24 | 3078426.5680693835 | 44901366.3 | 49100436.0 | 53050080.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### acquisition_v1 / inventory_infeasible / no_intervention

Objective: `new_customers` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 0; initial/final infeasibility: 100/100; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 5541.63 | 124.44457842750724 | 5384.6 | 5542.5 | 5682.0 |
| cac_minor | 100 | 0 | 134.92 | 3.051819129633996 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415317 | 0.007638010932173375 | 0.40669 | 0.41475 | 0.4252 |
| contribution_profit_minor | 100 | 0 | 49172232.24 | 3078426.5680693835 | 44901366.3 | 49100436.0 | 53050080.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### acquisition_v1 / standard / goal_conditioned_controller

Objective: `new_customers` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 100; initial/final infeasibility: 0/0; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 5586.12 | 119.99293979230612 | 5433.6 | 5582.5 | 5747.1 |
| cac_minor | 100 | 0 | 133.82 | 2.8683793333518492 | 130.0 | 134.0 | 138.0 |
| contribution_margin | 100 | 0 | 0.415396 | 0.007584680876609116 | 0.40657000000000004 | 0.41535 | 0.4253 |
| contribution_profit_minor | 100 | 0 | 49615720.2 | 3116868.282344071 | 45334322.0 | 49540944.5 | 53447455.4 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 11.0 | 0.0 | 11.0 | 11.0 | 11.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### acquisition_v1 / standard / no_intervention

Objective: `new_customers` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 100; initial/final infeasibility: 0/0; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 5541.63 | 124.44457842750724 | 5384.6 | 5542.5 | 5682.0 |
| cac_minor | 100 | 0 | 134.92 | 3.051819129633996 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415317 | 0.007638010932173375 | 0.40669 | 0.41475 | 0.4252 |
| contribution_profit_minor | 100 | 0 | 49172232.24 | 3078426.5680693835 | 44901366.3 | 49100436.0 | 53050080.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### excess_inventory_v1 / inventory_infeasible / goal_conditioned_controller

Objective: `units_sold` in `excess_inventory`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 0; initial/final infeasibility: 100/100; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 2154.99 | 447.2178550773661 | 1610.1 | 2110.5 | 2782.2000000000003 |
| cac_minor | 100 | 0 | 134.34 | 3.0206621790594195 | 131.0 | 135.0 | 138.10000000000002 |
| contribution_margin | 100 | 0 | 0.415565 | 0.008021027053937672 | 0.40569 | 0.41525 | 0.42621 |
| contribution_profit_minor | 100 | 0 | 48593715.59 | 2960116.5150362346 | 44682220.7 | 48396430.0 | 52799269.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### excess_inventory_v1 / inventory_infeasible / no_intervention

Objective: `units_sold` in `excess_inventory`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 0; initial/final infeasibility: 100/100; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 2154.99 | 447.2178550773661 | 1610.1 | 2110.5 | 2782.2000000000003 |
| cac_minor | 100 | 0 | 134.34 | 3.0206621790594195 | 131.0 | 135.0 | 138.10000000000002 |
| contribution_margin | 100 | 0 | 0.415565 | 0.008021027053937672 | 0.40569 | 0.41525 | 0.42621 |
| contribution_profit_minor | 100 | 0 | 48593715.59 | 2960116.5150362346 | 44682220.7 | 48396430.0 | 52799269.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### excess_inventory_v1 / standard / goal_conditioned_controller

Objective: `units_sold` in `excess_inventory`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 100; initial/final infeasibility: 0/0; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 2154.99 | 447.2178550773661 | 1610.1 | 2110.5 | 2782.2000000000003 |
| cac_minor | 100 | 0 | 134.34 | 3.0206621790594195 | 131.0 | 135.0 | 138.10000000000002 |
| contribution_margin | 100 | 0 | 0.415565 | 0.008021027053937672 | 0.40569 | 0.41525 | 0.42621 |
| contribution_profit_minor | 100 | 0 | 48593715.59 | 2960116.5150362346 | 44682220.7 | 48396430.0 | 52799269.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### excess_inventory_v1 / standard / no_intervention

Objective: `units_sold` in `excess_inventory`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 100; initial/final infeasibility: 0/0; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 2154.99 | 447.2178550773661 | 1610.1 | 2110.5 | 2782.2000000000003 |
| cac_minor | 100 | 0 | 134.34 | 3.0206621790594195 | 131.0 | 135.0 | 138.10000000000002 |
| contribution_margin | 100 | 0 | 0.415565 | 0.008021027053937672 | 0.40569 | 0.41525 | 0.42621 |
| contribution_profit_minor | 100 | 0 | 48593715.59 | 2960116.5150362346 | 44682220.7 | 48396430.0 | 52799269.3 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### search_conversion_v1 / inventory_infeasible / goal_conditioned_controller

Objective: `search_attributed_purchases` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 0; initial/final infeasibility: 100/100; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 1747.33 | 45.18474410683323 | 1688.6 | 1746.0 | 1808.0 |
| cac_minor | 100 | 0 | 134.95 | 3.05081956201936 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415368 | 0.007569965389617048 | 0.4065 | 0.4157 | 0.42491 |
| contribution_profit_minor | 100 | 0 | 49024151.08 | 3071059.510735667 | 44881335.8 | 48661686.5 | 52408078.300000004 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### search_conversion_v1 / inventory_infeasible / no_intervention

Objective: `search_attributed_purchases` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 0; initial/final infeasibility: 100/100; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 1747.33 | 45.18474410683323 | 1688.6 | 1746.0 | 1808.0 |
| cac_minor | 100 | 0 | 134.95 | 3.05081956201936 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415368 | 0.007569965389617048 | 0.4065 | 0.4157 | 0.42491 |
| contribution_profit_minor | 100 | 0 | 49024151.08 | 3071059.510735667 | 44881335.8 | 48661686.5 | 52408078.300000004 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### search_conversion_v1 / standard / goal_conditioned_controller

Objective: `search_attributed_purchases` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 100; initial/final infeasibility: 0/0; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 1747.33 | 45.18474410683323 | 1688.6 | 1746.0 | 1808.0 |
| cac_minor | 100 | 0 | 134.95 | 3.05081956201936 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415368 | 0.007569965389617048 | 0.4065 | 0.4157 | 0.42491 |
| contribution_profit_minor | 100 | 0 | 49024151.08 | 3071059.510735667 | 44881335.8 | 48661686.5 | 52408078.300000004 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### search_conversion_v1 / standard / no_intervention

Objective: `search_attributed_purchases` in `store`. Per-seed targets are retained in the raw rows.
Runs: 100; objective attained: 100; initial/final infeasibility: 0/0; paused: 0.
| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective_outcome | 100 | 0 | 1747.33 | 45.18474410683323 | 1688.6 | 1746.0 | 1808.0 |
| cac_minor | 100 | 0 | 134.95 | 3.05081956201936 | 131.0 | 135.0 | 139.0 |
| contribution_margin | 100 | 0 | 0.415368 | 0.007569965389617048 | 0.4065 | 0.4157 | 0.42491 |
| contribution_profit_minor | 100 | 0 | 49024151.08 | 3071059.510735667 | 44881335.8 | 48661686.5 | 52408078.300000004 |
| spend_minor | 100 | 0 | 750000.0 | 0.0 | 750000.0 | 750000.0 | 750000.0 |
| action_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rollback_count | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hard_policy_violations | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| outcome_guardrail_breaches | 100 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Interpretation and reproduction

A default goal can already be on track without intervention. Such rows cannot prove
the safety or benefit of an unexercised action. Observed economic guardrail breaches
are reported separately from hard dispatch/budget violations. Baseline infeasibility
is a read-only assessment, not baseline planning. No fixed-rule arm is implemented.

[Methods and reproduction commands](controller-v2.md).
[Raw release evidence](../../examples/eval/results/controller-v2-durable.json.gz).
Independent reproduction status is recorded in ../IMPLEMENTATION_STATUS.md, not
inferred from this generated report. Renderer: scripts/render-controller-report.py.
