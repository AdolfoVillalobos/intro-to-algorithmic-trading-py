from __future__ import annotations

import asyncio
import os

import aio_pika
import ccxt.pro as ccxt
from dotenv import load_dotenv
from logger_utils import get_logger
from models import TradeMessage
from pydantic import BaseModel
from pydantic import Field

logger = get_logger(__name__)


class Observer(BaseModel):
    symbol: str = Field(description="The symbol to observe")

    async def consume(self, exchange: ccxt.Exchange):
        while True:
            try:
                trades = await exchange.watch_my_trades()
                for trade in trades:
                    new_message = TradeMessage.from_ccxt(trade, exchange.id)
                    yield new_message
            except Exception as e:
                logger.error(f"Error watching {self.symbol}: {e}")

            finally:
                await asyncio.sleep(2)


async def producer(observer: Observer, exchange: ccxt.Exchange, rabbitmq_url: str):
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()

    try:
        async for trade_message in observer.consume(exchange):
            logger.info("New trade to %s: %s", trade_message.subject(), trade_message)
            message = aio_pika.Message(body=trade_message.model_dump_json().encode())
            await channel.default_exchange.publish(
                message,
                routing_key=trade_message.subject(),
            )
    finally:
        await connection.close()


async def load_exchange(exchange_name: str):
    logger.info(f"Loading {exchange_name} exchange")
    load_dotenv(".env")
    api_key = os.getenv(f"{exchange_name.upper()}_API_KEY")
    secret = os.getenv(f"{exchange_name.upper()}_API_SECRET")
    client = getattr(ccxt, exchange_name)(
        {
            "apiKey": api_key,
            "secret": secret,
            "options": {"newUpdates": True},
        }
    )
    await client.cancel_all_orders()
    return client


async def main() -> None:
    exchange_id = os.getenv("EXCHANGE_ID")
    exchange_name = os.getenv("EXCHANGE_NAME")

    exchange = await load_exchange(exchange_id)
    observer = Observer(symbol="BTC/USDT", exchange_id=exchange_name)
    await producer(observer, exchange, "amqp://guest:guest@rabbitmq/")


if __name__ == "__main__":
    asyncio.run(main())
