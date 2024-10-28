import asyncio
import logging
from pydantic import BaseModel
from typing import Callable
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




StrategyFn = Callable[[Arbitrage, PriceMessage], tuple[float, float]]


class Observer(BaseModel):


    async def on_price_update(self, message: aio_pika.IncomingMessage):
        logger.info(f"Received price update: {message.body}")


    async def subscribe(self, connection: aio_pika.Connection):
        channel = await connection.channel()
        queue = await channel.declare_queue("price_updates")

        await queue.consume(self.on_price_update)

        await asyncio.Future()



async def main():
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = Observer()
    await observer.subscribe(connection)


if __name__ == "__main__":
    asyncio.run(main())
