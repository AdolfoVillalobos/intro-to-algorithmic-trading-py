from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Order(BaseModel):
    symbol: str
    quantity: float
    price: float
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]

    def key(self) -> str:
        return f"{self.exchange}:{self.symbol}:{self.side}"
