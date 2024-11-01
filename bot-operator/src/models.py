from __future__ import annotations

from datetime import datetime
from typing import Literal
from typing import Optional

from pydantic import BaseModel


class PriceMessage(BaseModel):
    symbol: str
    ask_price: float
    bid_price: float
    datetime: datetime


class TradeMessage(BaseModel):
    symbol: str
    amount: float
    price: float
    exchange: str
    side: str
    datetime: datetime

    def subject(self) -> str:
        return f"trade_updates_{self.exchange}"


class Order(BaseModel):
    symbol: str
    quantity: float
    price: Optional[float]
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]

    def subject(self) -> str:
        return f"order_updates_{self.exchange}"


class Arbitrage(BaseModel):
    target_market: str
    origin_market: str
    target_exchange: str
    origin_exchange: str
    profit_threshold: float
    target_fee: float
    origin_fee: float

    def markup(self) -> float:
        return self.profit_threshold + self.target_fee + self.origin_fee

    def complete_arbitrage(self, trade_message: TradeMessage) -> Optional[Order]:
        if trade_message.symbol != self.target_market:
            return None

        if trade_message.exchange != self.target_exchange:
            return None

        oposite_side = "buy" if trade_message.side == "sell" else "sell"

        return Order(
            symbol=self.origin_market,
            quantity=trade_message.amount,
            price=None,
            side=oposite_side,
            exchange=self.origin_exchange,
            order_type="market",
        )
