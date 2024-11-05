from __future__ import annotations

from typing import Literal
from typing import Optional

from pydantic import BaseModel


class Order(BaseModel):
    symbol: str
    quantity: float
    price: Optional[float]
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]

    def key(self) -> str:
        return f"{self.exchange}:{self.symbol}:{self.side}"
