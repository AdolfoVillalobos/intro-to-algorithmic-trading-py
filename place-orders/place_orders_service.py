from __future__ import annotations

import asyncio
import json
import os
import signal

import aio_pika
import ccxt.async_support as ccxt
from dotenv import load_dotenv
from logger_utils import get_logger
from models import Order
from pydantic import BaseModel
from pydantic import Field

logger = get_logger(__name__)


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
    exchange_name: str
    last_order_ids: dict[str, str] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    async def on_order_update(self, message: aio_pika.IncomingMessage):
        try:
            logger.debug("Received order update from %s", message.routing_key)
            order = Order(**json.loads(message.body))
            if self.exchange is None:
                return

            if order.order_type == "limit":
                await self.execute_limit_order(order)
            elif order.order_type == "market":
                await self.execute_market_order(order)

        except Exception as e:
            logger.error(f"Error processing order update: {e}")

        finally:
            await message.ack()

    async def execute_limit_order(self, order: Order):
        try:
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
            logger.info(f"New order on {order.key()}: {result['id']}")
        except Exception as e:
            logger.error(f"Error executing limit order: {e} for {order.key()}")

    async def execute_market_order(self, order: Order):
        try:
            result = await self.exchange.create_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.quantity,
                type=order.order_type,
            )
            logger.warning(f"New order on {order.key()}: {result}")
        except Exception as e:
            logger.error(f"Error executing market order: {e} for {order.key()}")

    async def subscribe(self, connection: aio_pika.Connection):
        self.channel = await connection.channel()

        # Declare maker queue
        queue_name = f"order_updates_{self.exchange_name}"

        queue = await self.channel.declare_queue(queue_name)

        await queue.consume(self.on_order_update)

    async def close(self):
        if self.exchange:
            await self.exchange.cancel_all_orders()


async def main():
    load_dotenv(".env")
    exchange_id = os.getenv("EXCHANGE_ID")
    exchange_name = os.getenv("EXCHANGE_NAME")
    exchange = await load_exchange(exchange_id)
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = Observer(exchange=exchange, exchange_name=exchange_name)

    loop = asyncio.get_running_loop()
    main_task = asyncio.Future()

    def handle_sigterm():
        if not main_task.done():
            main_task.set_result(None)

    # Register SIGTERM handler
    loop.add_signal_handler(signal.SIGTERM, handle_sigterm)

    try:
        await observer.subscribe(connection)
        await main_task  # Wait until SIGTERM is received
    finally:
        await observer.close()
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
