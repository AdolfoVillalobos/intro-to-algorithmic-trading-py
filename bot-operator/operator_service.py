from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Literal
from typing import Optional

import aio_pika
import colorlog
from pydantic import BaseModel
from pydantic import Field

logger = logging.getLogger(__name__)
handler = colorlog.StreamHandler()
formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s %(levelname)-7s %(message)s%(reset)s",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "cyan",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    },
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


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


class MarketOrder(BaseModel):
    symbol: str
    quantity: float
    price: float
    side: Literal["buy", "sell"]
    exchange: str


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


class Order(BaseModel):
    symbol: str
    quantity: float
    price: Optional[float]
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]


Balance = dict[str, float]
StrategyFn = Callable[[Arbitrage, PriceMessage, Balance], list[Order]]


def simple_strategy(
    arbitrage: Arbitrage, price: PriceMessage, balances: Balance
) -> list[Order]:
    ask_price = price.ask_price * (1.0 + arbitrage.markup())
    bid_price = price.bid_price * (1.0 - arbitrage.markup())

    ask_quantity = balances["BTC"]
    bid_quantity = balances["USDT"] / ask_price
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


class Observer(BaseModel):
    arbitrage: Arbitrage
    strategy: StrategyFn
    channel: aio_pika.Channel | None = None
    balances: Balance = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    async def on_price_update(self, message: aio_pika.IncomingMessage):
        try:
            price = PriceMessage(**json.loads(message.body))
            orders = self.strategy(self.arbitrage, price, self.balances)

            # Publish orders to the order_updates queue
            for order in orders:
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=order.model_dump_json().encode()),
                    routing_key="order_updates",
                )
            logger.info(f"New decision: {order}")
        except Exception as e:
            logger.error(f"Error processing price update: {e}")

        finally:
            await message.ack()

    async def on_trade_update(self, message: aio_pika.IncomingMessage):
        try:
            trade = TradeMessage(**json.loads(message.body))
            order = self.arbitrage.complete_arbitrage(trade)
            if order:
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=order.model_dump_json().encode()),
                    routing_key=f"order_updates_{order.exchange}",
                )
        except Exception as e:
            logger.error(f"Error processing trade update: {e}")

        finally:
            await message.ack()

    async def subscribe(self, connection: aio_pika.Connection):
        self.channel = await connection.channel()

        # Declare price updates queue
        queue_price_updates = await self.channel.declare_queue("price_updates")
        await queue_price_updates.consume(self.on_price_update)

        # Declare limit updates queue
        _ = await self.channel.declare_queue(
            f"limit_updates_{self.arbitrage.target_exchange}"
        )

        # Declare taker updates queue
        queue_trades_updates = await self.channel.declare_queue(
            f"trades_updates_{self.arbitrage.target_exchange}"
        )
        await queue_trades_updates.consume(self.on_trade_update)

        await asyncio.Future()


async def main():
    arbitrage = Arbitrage(
        target_market="BTC/USD",
        origin_market="BTC/USDT",
        target_exchange="kraken",
        origin_exchange="binance",
        profit_threshold=0.05,
        target_fee=0.002,
        origin_fee=0.001,
    )
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = Observer(
        arbitrage=arbitrage,
        strategy=simple_strategy,
        balances={"BTC": 0.0003, "USDT": 0.0, "USD": 1000.0},
    )
    await observer.subscribe(connection)


if __name__ == "__main__":
    asyncio.run(main())