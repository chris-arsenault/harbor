# Hypothesis Log

This log is the durable index for Harbor research hypotheses. Each hypothesis is
an economic claim first, then an edge-search algorithm. Status values are
`proposed`, `active`, `rejected`, `archived`, `paused`, or `accepted-for-forward-test`.

| ID                                              | Status              | Edge algorithm                                                                                  | Hypothesis                                                                     |
| ----------------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| [H001](H001-generic-session-sweep-reversal.md)  | rejected            | `generic_sweep_reversal`                                                                        | Generic Asia/London session sweep predicts NY-window reversal.                 |
| [H002](H002-non-news-proxy-sweep-reversal.md)   | rejected / archived | `non_news_proxy_sweep_reversal`                                                                 | Archived sweep-reversal filter; no active strategy work.                       |
| [H003](H003-mss-confirmed-sweep-reversal.md)    | rejected / archived | `mss_confirmed_sweep_reversal`                                                                  | Archived MSS-confirmed sweep reversal; did not rescue the family.              |
| [H004](H004-compressed-range-sweep-reversal.md) | rejected / archived | `compressed_range_sweep_reversal`                                                               | Archived compressed-range sweep reversal; no material corrected edge.          |
| [H005](H005-clean-level-sweep-reversal.md)      | rejected            | `clean_level_sweep_reversal`                                                                    | GBP_JPY clean first-touch reversal failed the larger-sample confirmatory scan. |
| [H006](H006-early-ny-sweep-reversal.md)         | rejected / archived | `early_ny_sweep_reversal`                                                                       | Archived early-NY sweep reversal; did not beat rejected baseline.              |
| [H007](H007-eurusd-sweep-continuation.md)       | paused / archived   | `generic_sweep_continuation`, `mss_confirmed_sweep_continuation`, `early_ny_sweep_continuation` | Archived EUR_USD sweep continuation; directionally coherent but cost-thin.     |

| [H100](H100-cross-sectional-fx-factors.md) | rejected / archived | `cs_momentum_20d_5d`, `cs_value_60d_5d` | Archived factor baskets: momentum inverted; value/reversion weak. |
| [H101](H101-triangular-residual-convergence.md) | active / promising, cost-capture testing | `tri_eur_gbp_residual_5d` | EUR/GBP triangular residual convergence; strongest signal so far (t≈4.6, small N). |
| [H102](H102-usd-dispersion-reversion.md) | rejected | `usd_dispersion_reversion_5d` | Corrected USD-factor dispersion reversion rerun showed no material signal. |
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
