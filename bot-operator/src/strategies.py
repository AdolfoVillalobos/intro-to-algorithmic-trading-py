from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from models import Arbitrage
from models import Order
from models import PriceMessage


class TradingStrategy(ABC):
    @abstractmethod
    def execute(
        self, arbitrage: Arbitrage, price: PriceMessage, amount_to_trade_usdt: float
    ) -> list[Order]:
        pass


class SimpleStrategy(TradingStrategy):
    def execute(
        self, arbitrage: Arbitrage, price: PriceMessage, amount_to_trade_usdt: float
    ) -> list[Order]:
        ask_price = price.ask_price * (1.0 + arbitrage.markup())
        bid_price = price.bid_price * (1.0 - arbitrage.markup())

        ask_quantity = amount_to_trade_usdt / ask_price
        bid_quantity = amount_to_trade_usdt / bid_price
        return [
            Order(
                symbol=arbitrage.target_market,
                quantity=bid_quantity,
                price=bid_price,
                side="buy",
                exchange=arbitrage.target_exchange,
                order_type="limit",
            ),
            Order(
                symbol=arbitrage.target_market,
                quantity=ask_quantity,
                price=ask_price,
                side="sell",
                exchange=arbitrage.target_exchange,
                order_type="limit",
            ),
        ]
