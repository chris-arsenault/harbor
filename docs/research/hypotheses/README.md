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
| [H005](H005-clean-level-sweep-reversal.md) | rejected | `clean_level_sweep_reversal` | GBP_JPY clean first-touch reversal failed the larger-sample confirmatory scan. |
| [H006](H006-early-ny-sweep-reversal.md) | proposed | `early_ny_sweep_reversal` | NY opening-auction sweeps behave differently from late-window sweeps. |
| [H007](H007-eurusd-sweep-continuation.md) | active / cost-capture testing | `generic_sweep_continuation`, `mss_confirmed_sweep_continuation`, `early_ny_sweep_continuation` | EUR_USD sweeps show continuation signal; next gate is net capture after costs. |

| [H100](H100-cross-sectional-fx-factors.md) | active / research engine implemented | `cs_momentum_20d_5d`, `cs_value_60d_5d` | Cross-sectional FX momentum and value/reversion baskets. |
| [H101](H101-triangular-residual-convergence.md) | active / research engine implemented | `tri_eur_gbp_residual_5d` | EUR/GBP triangular residual convergence. |
| [H102](H102-usd-dispersion-reversion.md) | active / research engine implemented | `usd_dispersion_reversion_5d` | USD-factor dispersion reversion. |
| [H103](H103-oanda-positioning-orderbook.md) | proposed / data recorder needed | future OANDA positioning/order-book algorithms | Retail positioning and visible liquidity clusters. |
| [H104](H104-rates-yield-conditioning.md) | proposed / external data layer needed | future rates conditioning | FX edge conditioned on yield differentials. |
| [H105](H105-risk-commodity-conditioning.md) | proposed / external data layer needed | future risk/commodity conditioning | JPY/AUD pairs conditioned on risk and commodity state. |
| [H106](H106-month-end-fix-flow.md) | proposed / calendar input needed | future month-end/fix algorithms | Forced hedge-rebalancing flow around month-end / London fix. |
| [H107](H107-scheduled-event-surprise.md) | proposed / calendar + surprise data needed | future macro surprise algorithms | Scheduled event drift conditioned on surprise. |

## Research gate

Do not promote a strategy variant from a hypothesis unless its edge algorithm
shows a statistically meaningful base-rate skew after clustered standard errors,
multiple-test adjustment, cost sanity checks, walk-forward validation, and
paper-forward evidence.
