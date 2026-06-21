from dataclasses import dataclass
from decimal import Decimal

from harbor_bot.strategy.models import InstrumentRules

RESEARCH_INSTRUMENTS = (
    "GBP_USD",
    "EUR_USD",
    "USD_JPY",
    "EUR_JPY",
    "GBP_JPY",
    "AUD_JPY",
    "AUD_USD",
    "EUR_GBP",
)


@dataclass(frozen=True)
class InstrumentSpec:
    instrument: str
    pip_location: int
    display_precision: int
    trade_units_precision: int = 0
    minimum_trade_size: Decimal = Decimal("1")
    unit_step: Decimal = Decimal("1")
    quote_home_conversion: Decimal = Decimal("1")

    def to_rules(self) -> InstrumentRules:
        return InstrumentRules(
            instrument=self.instrument,
            pip_location=self.pip_location,
            display_precision=self.display_precision,
            trade_units_precision=self.trade_units_precision,
            minimum_trade_size=self.minimum_trade_size,
            unit_step=self.unit_step,
            quote_home_conversion=self.quote_home_conversion,
        )


def default_instrument_rules(instrument: str) -> InstrumentRules:
    return default_instrument_spec(instrument).to_rules()


def default_instrument_spec(instrument: str) -> InstrumentSpec:
    if instrument.endswith("_JPY"):
        return InstrumentSpec(
            instrument=instrument,
            pip_location=-2,
            display_precision=3,
        )
    return InstrumentSpec(
        instrument=instrument,
        pip_location=-4,
        display_precision=5,
    )
