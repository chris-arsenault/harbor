# H109 — Regime-conditioned resurrection of dead signals

- Status: active / exploratory probe implemented
- Algorithm: `regime_resurrection_probe`

## Hypothesis

Some rejected price-derived signals are not universally wrong; they are wrong in
the wrong regime. The clearest candidate is H100 momentum, which was
significantly negative. Cross-sectional momentum may be an inverse-momentum /
reversal effect in specific volatility regimes.

## Economic rationale

FX alternates between macro-trending and liquidity-reverting regimes. A signal
that averages to zero can still be useful if the sign or payoff distribution is
regime-stable.

## Initial test

The probe inverts the H100 20d→5d momentum leg and splits observations into
low/mid/high realized-volatility terciles. Each tercile reports mean reversal bps
and t-stat. Records stride by the 5-day holding horizon so forward windows do
not overlap; the t-stats are honest but the probe needs a correspondingly longer
history (~1.5 years) before terciles fill. The unconditional version of this
effect is promoted separately as H113.

## Gate

Promote only if one regime has a clear positive effect, neighboring regimes do
not contradict it, and a follow-up walk-forward test fixes the regime definition
before scoring.
