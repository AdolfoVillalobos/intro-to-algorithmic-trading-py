import asyncio
import logging
import json
from pydantic import BaseModel
from typing import Callable, Literal
from datetime import datetime
import aio_pika

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(filename)-15s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class PriceMessage(BaseModel):
    symbol: str
    ask_price: float
    bid_price: float
    datetime: datetime


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

class Order(BaseModel):
    symbol: str
    quantity: float
    price: float
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]


StrategyFn = Callable[[Arbitrage, PriceMessage], list[Order]]


def simple_strategy(arbitrage: Arbitrage, price: PriceMessage) -> list[Order]:
    ask_price = price.ask_price * (1.0 + arbitrage.markup())
    bid_price = price.bid_price * (1.0 - arbitrage.markup())
    return [
        Order(
            symbol=arbitrage.target_market,
            quantity=1.0,
            price=bid_price,
            side="buy",
            exchange=arbitrage.target_exchange,
            order_type="limit",
        ),
        Order(
            symbol=arbitrage.target_market,
            quantity=1.0,
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

    class Config:
        arbitrary_types_allowed = True

    async def on_price_update(self, message: aio_pika.IncomingMessage):
        price = PriceMessage(**json.loads(message.body))
        logger.info(f"Received price update: {price}")
        orders = self.strategy(self.arbitrage, price)

        # Publish orders to the order_updates queue
        for order in orders:
            await self.channel.default_exchange.publish(
                aio_pika.Message(body=order.model_dump_json().encode()),
                routing_key="order_updates"
            )
            logger.info(f"Published order: {order}")



    async def subscribe(self, connection: aio_pika.Connection):
        self.channel = await connection.channel()
        queue = await self.channel.declare_queue("price_updates")

        await self.channel.declare_queue("order_updates")

        await queue.consume(self.on_price_update)

        await asyncio.Future()


async def main():
    arbitrage = Arbitrage(
        target_market="BTC/USD",
        origin_market="BTC/USDT",
        target_exchange="kraken",
        origin_exchange="binance",
        profit_threshold=0.01,
        target_fee=0.002,
        origin_fee=0.001,
    )
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = Observer(arbitrage=arbitrage, strategy=simple_strategy)
    await observer.subscribe(connection)


if __name__ == "__main__":
    asyncio.run(main())
