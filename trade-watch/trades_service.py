from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import aio_pika
import ccxt.pro as ccxt
import colorlog
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic import Field


logger = logging.getLogger(__name__)
handler = colorlog.StreamHandler()
formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s %(levelname)-7s %(message)s%(reset)s",
    log_colors={
        "DEBUG": "blue",
        "INFO": "blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    },
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class TradeMessage(BaseModel):
    symbol: str
    amount: float
    price: float
    exchange: str
    side: str
    datetime: datetime

    def __str__(self) -> str:
        return f"{self.symbol} {self.side} {self.amount} @ {self.price}"

    @classmethod
    def from_ccxt(cls, trade: dict, exchange_id: str):
        try:
            if trade["timestamp"] is None:
                dt = datetime.now()
            else:
                dt = datetime.fromtimestamp(float(trade["timestamp"]) / 1000)
            return cls(
                datetime=dt,
                symbol=trade["symbol"],
                amount=trade["amount"],
                price=trade["price"],
                exchange=exchange_id,
                side=trade["side"],
            )
        except Exception as e:
            logger.error(f"Error parsing trade {trade}: {e}")
            return None


class Observer(BaseModel):
    symbol: str = Field(description="The symbol to observe")

    async def consume(self, exchange: ccxt.Exchange):
        while True:
            try:
                trades = await exchange.watch_my_trades()
                for trade in trades:
                    new_message = TradeMessage.from_ccxt(trade, exchange.id)
                    logger.info(f"Observed from {exchange.id}: {new_message}")
                    yield new_message
            except Exception as e:
                logger.error(f"Error watching {self.symbol}: {e}")

            finally:
                await asyncio.sleep(2)


async def producer(observer: Observer, exchange: ccxt.Exchange, rabbitmq_url: str):
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    queue_name = f"trade_updates_{observer.exchange_id}"
    logger.info(f"Declaring queue {queue_name}")
    queue = await channel.declare_queue(queue_name)

    try:
        async for trade_message in observer.consume(exchange):
            message = aio_pika.Message(body=trade_message.model_dump_json().encode())
            await channel.default_exchange.publish(
                message,
                routing_key=queue.name,
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
    exchange = await load_exchange("bitfinex2")
    observer = Observer(symbol="BTC/USDT", exchange_id="bitfinex")
    await producer(observer, exchange, "amqp://guest:guest@rabbitmq/")


if __name__ == "__main__":
    asyncio.run(main())
