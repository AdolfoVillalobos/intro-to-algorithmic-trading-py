import asyncio
import logging
import json
from pydantic import BaseModel
from typing import Literal
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


class Order(BaseModel):
    symbol: str
    quantity: float
    price: float
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]


class Observer(BaseModel):
    channel: aio_pika.Channel | None = None

    class Config:
        arbitrary_types_allowed = True

    async def on_order_update(self, message: aio_pika.IncomingMessage):
        order = Order(**json.loads(message.body))
        logger.info(f"Received order update: {order}")

    async def subscribe(self, connection: aio_pika.Connection):
        self.channel = await connection.channel()
        queue = await self.channel.declare_queue("order_updates")

        await queue.consume(self.on_order_update)

        await asyncio.Future()


async def main():
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = Observer()
    await observer.subscribe(connection)


if __name__ == "__main__":
    asyncio.run(main())
