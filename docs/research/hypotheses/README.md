# Hypothesis Log

This log is the durable index for Harbor research hypotheses. Each hypothesis is
an economic claim first, then an edge-search algorithm. Status values are
`proposed`, `active`, `rejected`, or `accepted-for-forward-test`.

| ID | Status | Edge algorithm | Hypothesis |
| --- | --- | --- | --- |
| [H001](H001-generic-session-sweep-reversal.md) | rejected | `generic_sweep_reversal` | Generic Asia/London session sweep predicts NY-window reversal. |
| [H002](H002-non-news-proxy-sweep-reversal.md) | proposed | `non_news_proxy_sweep_reversal` | Sweep reversals are more likely outside the 10:00 ET macro-release proxy window. |
| [H003](H003-mss-confirmed-sweep-reversal.md) | proposed | `mss_confirmed_sweep_reversal` | A sweep only has reversal edge after market-structure shift confirmation. |
| [H004](H004-compressed-range-sweep-reversal.md) | proposed | `compressed_range_sweep_reversal` | Sweeps after compressed Asia/London range have cleaner reversal behavior. |
| [H005](H005-clean-level-sweep-reversal.md) | proposed | `clean_level_sweep_reversal` | First-touch clean levels carry more signal than repeatedly tapped levels. |
| [H006](H006-early-ny-sweep-reversal.md) | proposed | `early_ny_sweep_reversal` | NY opening-auction sweeps behave differently from late-window sweeps. |

## Research gate

Do not promote a strategy variant from a hypothesis unless its edge algorithm
shows a statistically meaningful base-rate skew after clustered standard errors,
multiple-test adjustment, cost sanity checks, walk-forward validation, and
paper-forward evidence.
