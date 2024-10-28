import ccxt
import ccxt.pro
from datetime import datetime
from pydantic import BaseModel, Field

import logging

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)-7s %(filename)-15s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class PriceMessage(BaseModel):
    symbol: str
    ask_price: float
    bid_price: float
    datetime: datetime

    @classmethod
    def from_orderbook(cls, orderbook: dict):
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
                )
        except Exception as e:
            logger.error(f"Error parsing orderbook {orderbook}: {e}")
            return None

    def has_changed(self, other: "PriceMessage", threshold: float = 0.0001) -> bool:
        ask_diff_pct = abs(self.ask_price - other.ask_price) / self.ask_price
        bid_diff_pct = abs(self.bid_price - other.bid_price) / self.bid_price
        return ask_diff_pct > threshold or bid_diff_pct > threshold


class Observer(BaseModel):
    symbol: str = Field(description="The symbol to observe")
    last_message: PriceMessage | None = None

    async def watch(self, exchange: ccxt.Exchange):
        while True:
            try:
                orderbook = await exchange.watch_order_book(self.symbol)
                new_message = PriceMessage.from_orderbook(orderbook)

                if self.last_message is None or self.last_message.has_changed(new_message):
                    logger.info(f"Observed {new_message}")
                    self.last_message = new_message

            except Exception as e:
                logger.error(f"Error watching {self.symbol}: {e}")

            await asyncio.sleep(1)


async def main() -> None:
    exchange = ccxt.pro.binance()
    observer = Observer(symbol="BTC/USDT")
    await observer.watch(exchange)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
