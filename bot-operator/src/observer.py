from __future__ import annotations

import json
from abc import ABC
from abc import abstractmethod

import aio_pika
from models import Arbitrage
from models import Order
from models import PriceMessage
from pydantic import BaseModel
from src.logger_utils import get_logger
from strategies import SimpleStrategy
from strategies import TradingStrategy

logger = get_logger(__name__)


class MarketEventListener(ABC):
    @abstractmethod
    async def on_price_update(self, message: aio_pika.IncomingMessage):
        pass

    @abstractmethod
    async def on_trade_update(self, message: aio_pika.IncomingMessage):
        pass


class ArbitrageObserver(MarketEventListener, BaseModel):
    arbitrage: Arbitrage
    strategy: TradingStrategy
    channel: aio_pika.Channel | None = None
    amount_to_trade_usdt: float

    class Config:
        arbitrary_types_allowed = True

    def target_exchange(self) -> str:
        return self.arbitrage.target_exchange

    def origin_exchange(self) -> str:
        return self.arbitrage.origin_exchange

    async def _publish_order(self, order: Order):
        if not self.channel:
            raise RuntimeError("Channel not initialized")
        subject = order.subject()
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=order.model_dump_json().encode()),
            routing_key=subject,
        )
        logger.info("New decision to %s: %s", subject, order)

    async def on_price_update(self, message: aio_pika.IncomingMessage):
        try:
            logger.info("Received price update from %s", message.routing_key)
            price = PriceMessage(**json.loads(message.body))
            orders = self.strategy.execute(
                self.arbitrage, price, self.amount_to_trade_usdt
            )

            for order in orders:
                await self._publish_order(order)
        except Exception as e:
            logger.error("Error processing price update: %s", e)
        finally:
            await message.ack()

    # ... rest of the Observer class remains the same ...


async def main():
    arbitrage = Arbitrage(
        target_market="BTC/USDT",
        origin_market="BTC/USDT",
        target_exchange="bitfinex",
        origin_exchange="kraken",
        profit_threshold=0.05,
        target_fee=0.002,
        origin_fee=0.001,
    )
    connection = await aio_pika.connect("amqp://guest:guest@rabbitmq/")
    observer = ArbitrageObserver(
        arbitrage=arbitrage,
        strategy=SimpleStrategy(),
        amount_to_trade_usdt=15.0,
    )
    await observer.subscribe(connection)
