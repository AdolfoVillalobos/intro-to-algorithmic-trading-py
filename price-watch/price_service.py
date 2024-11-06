from __future__ import annotations

import asyncio
import os
from abc import ABC
from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Optional

import aio_pika
import ccxt.pro
from dotenv import load_dotenv
from logger_utils import get_logger
from models import PriceMessage
from pydantic import BaseModel

logger = get_logger(__name__)


class PriceSource(BaseModel, ABC):
    """Abstract base class for different price data sources"""

    @abstractmethod
    async def watch_prices(self, symbol: str) -> AsyncIterator[PriceMessage]:
        pass


class CCXTPriceSource(PriceSource):
    """Generate prices from a CCXT client"""

    exchange: ccxt.Exchange
    exchange_name: str

    class Config:
        arbitrary_types_allowed = True

    async def watch_prices(self, symbol: str) -> AsyncIterator[PriceMessage]:
        last_message = None
        while True:
            try:
                orderbook = await self.exchange.watch_order_book(symbol)
                new_message = PriceMessage.from_orderbook(orderbook, self.exchange_name)

                if last_message is None or last_message.has_changed(new_message):
                    last_message = new_message
                    yield new_message
            except Exception as e:
                logger.error(f"Error watching {symbol}: {e}")
            finally:
                await asyncio.sleep(10)


class MessageQueuePublisher(BaseModel):
    channel: Optional[aio_pika.Channel] = None
    connection: Optional[aio_pika.Connection] = None

    class Config:
        arbitrary_types_allowed = True

    async def connect(self, rabbitmq_url: str):
        self.connection = await aio_pika.connect_robust(rabbitmq_url)
        self.channel = await self.connection.channel()

    async def publish(self, message: PriceMessage):
        if self.channel is None:
            self.channel = await self.connection.channel()
        logger.info("Publishing price message to %s: %s", message.subject(), message)
        amqp_message = aio_pika.Message(body=message.model_dump_json().encode())
        await self.channel.default_exchange.publish(
            amqp_message,
            routing_key=message.subject(),
        )

    async def close(self):
        if self.connection:
            await self.connection.close()


async def price_service(
    price_source: PriceSource,
    publisher: MessageQueuePublisher,
    symbol: str,
    rabbitmq_url: str,
) -> None:
    try:
        await publisher.connect(rabbitmq_url)
        async for price_message in price_source.watch_prices(symbol):
            await publisher.publish(price_message)
    finally:
        await publisher.close()


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

    price_source = CCXTPriceSource(exchange=exchange, exchange_name=exchange_name)
    publisher = MessageQueuePublisher()

    await price_service(
        price_source, publisher, "BTC/USDT", "amqp://guest:guest@rabbitmq/"
    )


if __name__ == "__main__":
    asyncio.run(main())
