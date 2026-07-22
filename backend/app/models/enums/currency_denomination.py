from enum import Enum
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Mapping


class CurrencyDenomination(str, Enum):
    COPPER = "cp"
    SILVER = "sp"
    ELECTRUM = "ep"
    GOLD = "gp"
    PLATINUM = "pp"

    @property
    def value_in_gp(self) -> Decimal:
        return CURRENCY_VALUES_IN_GP[self]


CURRENCY_VALUES_IN_GP: Final[Mapping[CurrencyDenomination, Decimal]] = (
    MappingProxyType(
        {
            CurrencyDenomination.COPPER: Decimal("0.01"),
            CurrencyDenomination.SILVER: Decimal("0.1"),
            CurrencyDenomination.ELECTRUM: Decimal("0.5"),
            CurrencyDenomination.GOLD: Decimal("1"),
            CurrencyDenomination.PLATINUM: Decimal("10"),
        }
    )
)
