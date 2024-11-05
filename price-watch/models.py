from __future__ import annotations

from datetime import datetime

from logger_utils import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)


class PriceMessage(BaseModel):
    symbol: str
    ask_price: float
    bid_price: float
    datetime: datetime
    exchange: str

    def __str__(self) -> str:
        return f"{self.symbol} ask={self.ask_price} bid={self.bid_price}"

    def subject(self) -> str:
        return f"price_updates_{self.exchange}"

    @classmethod
    def from_orderbook(cls, orderbook: dict, exchange: str):
        try:
            if orderbook["timestamp"] is None:
                dt = datetime.now()
            else:
                dt = datetime.fromtimestamp(float(orderbook["timestamp"]) / 1000)
            return cls(
                datetime=dt,
                symbol=orderbook["symbol"],
                ask_price=orderbook["asks"][0][0],
                bid_price=orderbook["bids"][0][0],
                exchange=exchange,
            )
        except Exception as e:
            logger.error(f"Error parsing orderbook {orderbook}: {e}")
            return None

    def has_changed(self, other: "PriceMessage", threshold: float = 0.0001) -> bool:
        ask_diff_pct = abs(self.ask_price - other.ask_price) / self.ask_price
        bid_diff_pct = abs(self.bid_price - other.bid_price) / self.bid_price
        return ask_diff_pct > threshold or bid_diff_pct > threshold
