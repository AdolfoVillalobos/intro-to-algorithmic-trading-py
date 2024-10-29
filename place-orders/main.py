from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Literal

import aio_pika
import ccxt.async_support as ccxt
import colorlog
from dotenv import load_dotenv
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


class Order(BaseModel):
    symbol: str
    quantity: float
    price: float
    side: Literal["buy", "sell"]
    exchange: str
    order_type: Literal["market", "limit"]

    def key(self) -> str:
        return f"{self.exchange}:{self.symbol}:{self.side}"


async def load_exchange(exchange_name: str):
    api_key = os.getenv(f"{exchange_name.upper()}_API_KEY")
    secret = os.getenv(f"{exchange_name.upper()}_API_SECRET")
    client = getattr(ccxt, exchange_name)(
        {
            "apiKey": api_key,
            "secret": secret,
        }
    )
    await client.load_markets()
    await client.cancel_all_orders()
    return client


class Observer(BaseModel):
    channel: aio_pika.Channel | None = None
    exchange: ccxt.Exchange | None = None
    last_order_ids: dict[str, str] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    async def on_order_update(self, message: aio_pika.IncomingMessage):
        try:
            order = Order(**json.loads(message.body))
            if self.exchange is None:
                return

            last_order_id = self.last_order_ids.get(order.key())

            if last_order_id is not None:
                logger.debug(f"Cancelling on {order.key()}: {last_order_id}")
                await self.exchange.cancel_order(last_order_id)

            if order.quantity == 0:
                logger.warning(f"Skipping on {order.key()}: quantity is 0")
                return

            result = await self.exchange.create_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.quantity,
                price=order.price,
                type=order.order_type,
            )
            self.last_order_ids[order.key()] = result["id"]
            logger.debug(f"New order on {order.key()}: {result['id']}")
        except Exception as e:
            logger.error(f"Error processing order update: {e}")

        finally:
            await message.ack()

    async def subscribe(self, connection: aio_pika.Connection):
        self.channel = await connection.channel()
        queue = await self.channel.declare_queue("order_updates")

        await queue.consume(self.on_order_update)

        await asyncio.Future()


async def main():
    load_dotenv(".env")
    exchange = await load_exchange("kraken")
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = Observer(exchange=exchange)
    await observer.subscribe(connection)


if __name__ == "__main__":
    asyncio.run(main())
