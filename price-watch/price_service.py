from __future__ import annotations

import asyncio
import os

import aio_pika
import ccxt.pro
from dotenv import load_dotenv
from logger_utils import get_logger
from models import PriceMessage
from pydantic import BaseModel
from pydantic import Field

logger = get_logger(__name__)


class Observer(BaseModel):
    exchange_name: str
    symbol: str = Field(description="The symbol to observe")
    last_message: PriceMessage | None = None

    async def watch(self, exchange: ccxt.Exchange):
        while True:
            try:
                orderbook = await exchange.watch_order_book(self.symbol)
                new_message = PriceMessage.from_orderbook(orderbook, self.exchange_name)

                if self.last_message is None or self.last_message.has_changed(
                    new_message
                ):
                    self.last_message = new_message
                    yield new_message
            except Exception as e:
                logger.error(f"Error watching {self.symbol}: {e}")

            finally:
                await asyncio.sleep(2)


async def producer(observer: Observer, exchange: ccxt.Exchange, rabbitmq_url: str):
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()

    try:
        async for price_message in observer.watch(exchange):
            logger.info(
                "Publishing price message to %s: %s",
                price_message.subject(),
                price_message,
            )
            message = aio_pika.Message(body=price_message.model_dump_json().encode())
            await channel.default_exchange.publish(
                message,
                routing_key=price_message.subject(),
            )
    finally:
        await connection.close()


async def load_exchange(exchange_name: str):
    client = getattr(ccxt.pro, exchange_name)()
    await client.load_markets()
    return client


async def main() -> None:
    load_dotenv(".env")
    exchange_id = os.getenv("EXCHANGE_ID")
    exchange_name = os.getenv("EXCHANGE_NAME")
    logger.info("Loading exchange %s", exchange_id)
    exchange = await load_exchange(exchange_id)
    observer = Observer(symbol="BTC/USDT", exchange_name=exchange_name)
    await producer(observer, exchange, "amqp://guest:guest@rabbitmq/")


if __name__ == "__main__":
    asyncio.run(main())
