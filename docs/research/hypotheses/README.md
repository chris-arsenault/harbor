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
| [H101](H101-triangular-residual-convergence.md) | paused / archived | `tri_eur_gbp_residual_5d` | EUR/GBP triangular residual convergence: structural but underpowered/cost-sensitive. |
| [H102](H102-usd-dispersion-reversion.md) | rejected | `usd_dispersion_reversion_5d` | Corrected USD-factor dispersion reversion rerun showed no material signal. |
| [H103](H103-oanda-positioning-orderbook.md) | proposed / data recorder needed | future OANDA positioning/order-book algorithms | Retail positioning and visible liquidity clusters. |
| [H104](H104-rates-yield-conditioning.md) | proposed / external data layer needed | future rates conditioning | FX edge conditioned on yield differentials. |
| [H105](H105-risk-commodity-conditioning.md) | proposed / external data layer needed | future risk/commodity conditioning | JPY/AUD pairs conditioned on risk and commodity state. |
| [H106](H106-month-end-fix-flow.md) | active / exploratory | `month_end_fix_probe` | Forced hedge-rebalancing flow around month-end / London fix. |
| [H107](H107-scheduled-event-surprise.md) | proposed / calendar + surprise data needed | future macro surprise algorithms | Scheduled event drift conditioned on surprise. |
| [H108](H108-weekend-risk-gap.md) | active / data-gated | `weekend_risk_gap_probe` | Weekend 24/7 risk-asset information gap: reopen gap vs post-reopen drift legs. |
| [H109](H109-regime-resurrection.md) | active / exploratory | `regime_resurrection_probe` | Regime-conditioned resurrection of dead/inverted signals. |
| [H110](H110-volatility-target.md) | active / exploratory | `range_forecast_probe` | HAR-style next-day range forecast instead of direction. |
| [H111](H111-book-conditioned-sweeps.md) | active / awaiting H103 data | `book_conditioner_readiness` | Book state as sweep conditioner: trapped crowd and underwater-long fade. |
| [H112](H112-lead-lag-network.md) | active / exploratory | `lead_lag_network_probe` | Currency-network lead/lag propagation timing (family FDR-gated). |
| [H113](H113-cross-sectional-reversal.md) | active / candidate | `cs_reversal_20d_5d_tranched` | Vol-scaled, tranched cross-sectional reversal (inverted H100 momentum). |
| [H114](H114-cross-pair-sweep-divergence.md) | active / exploratory | `sweep_divergence_probe` | Sibling-confirmed sweeps continue; divergent sweeps revert. |
| [H115](H115-multi-candle-sweep-reclaim.md) | active / exploratory | `multi_candle_sweep_reclaim_reversal` | Slow breach-then-reclaim sweeps the single-candle definition misses. |
| [H116](H116-triple-barrier-sweep-outcomes.md) | active / exploratory | `run_barrier_scan` barrier scoring | First-touch ±k·ATR barrier outcomes; meta-label training target. |

## Research gate

Do not promote a strategy variant from a hypothesis unless its edge algorithm
shows a statistically meaningful base-rate skew after clustered standard errors,
multiple-test adjustment, cost sanity checks, walk-forward validation, and
paper-forward evidence.

Multiple-test control is two-tier: exploratory scans use Benjamini-Hochberg FDR
across the scan family (Bonferroni across a whole universe scan demands
per-event effects larger than any realistic FX edge), and any FDR survivor must
then pass a single pre-registered confirmatory rerun under the Bonferroni gate.
For power, prefer ATR-normalized outcomes, the pooled multi-instrument panel
scan (`POST /api/research/edge/pooled`), and barrier first-touch scoring
(`POST /api/research/edge/barriers`) over raw fixed-horizon pip means.
