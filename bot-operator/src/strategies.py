from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from src.models import Arbitrage
from src.models import Order
from src.models import PriceMessage
from src.models import TradeMessage


class TradingStrategy(ABC):
    """
    A trading strategy is a class that generates orders based on events.
    """

    @abstractmethod
    def generate_limit_orders(
        self, arbitrage: Arbitrage, price: PriceMessage, amount_to_trade_usdt: float
    ) -> list[Order]:
        pass

    @abstractmethod
    def generate_market_orders(
        self, arbitrage: Arbitrage, trade_message: TradeMessage
    ) -> list[Order]:
        pass


class SimpleStrategy(TradingStrategy):
    def generate_limit_orders(
        self, arbitrage: Arbitrage, price: PriceMessage, amount_to_trade_usdt: float
    ) -> list[Order]:
        ask_price = price.ask_price * (1.0 + arbitrage.markup())

        ask_quantity = amount_to_trade_usdt / ask_price
        return [
            Order(
                symbol=arbitrage.target_market,
                quantity=ask_quantity,
                price=ask_price,
                side="sell",
                exchange=arbitrage.target_exchange,
                order_type="limit",
            ),
        ]

    def generate_market_orders(
        self, arbitrage: Arbitrage, trade_message: TradeMessage
    ) -> list[Order]:
        if trade_message.symbol != arbitrage.target_market:
            return []

        if trade_message.exchange != arbitrage.target_exchange:
            return []

        oposite_side = "buy" if trade_message.side == "sell" else "sell"

        return [
            Order(
                symbol=arbitrage.origin_market,
                quantity=trade_message.amount,
                price=None,
                side=oposite_side,
                exchange=arbitrage.origin_exchange,
                order_type="market",
            )
        ]
