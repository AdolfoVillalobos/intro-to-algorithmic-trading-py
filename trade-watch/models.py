from __future__ import annotations

from datetime import datetime

from logger_utils import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)


class TradeMessage(BaseModel):
    symbol: str
    amount: float
    price: float
    exchange: str
    side: str
    datetime: datetime

    def subject(self) -> str:
        return f"trade_updates_{self.exchange}"

    def __str__(self) -> str:
        return f"{self.symbol} {self.side} {self.amount} @ {self.price}"

    @classmethod
    def from_ccxt(cls, trade: dict, exchange_id: str):
        try:
            if trade["timestamp"] is None:
                dt = datetime.now()
            else:
                dt = datetime.fromtimestamp(float(trade["timestamp"]) / 1000)
            return cls(
                datetime=dt,
                symbol=trade["symbol"],
                amount=trade["amount"],
                price=trade["price"],
                exchange=exchange_id,
                side=trade["side"],
            )
        except Exception as e:
            logger.error(f"Error parsing trade {trade}: {e}")
            return None
