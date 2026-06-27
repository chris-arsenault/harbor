# H002 — Non-news-proxy sweep reversal

- Status: proposed
- Edge algorithm: `non_news_proxy_sweep_reversal`

## Hypothesis

Sweeps outside the 10:00 ET macro-release proxy window have a stronger reversal
profile than generic sweeps.

## Economic rationale

Scheduled macro events can cause genuine repricing and continuation rather than
stop-run mean reversion. Removing the common 10:00 ET release window should reduce
news-driven noise if the liquidity-run premise is valid outside news.

## Current implementation

The edge algorithm excludes sweeps whose closed candle is between 09:55 and 10:10
America/New_York. This is a proxy, not a real economic calendar.

## Pass condition

A corrected edge scan must show positive mean reversal, sufficient effective NY
trading-day samples, corrected t >= 2, and multiple-test-adjusted p <= 0.025.
