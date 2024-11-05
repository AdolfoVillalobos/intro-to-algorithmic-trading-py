from __future__ import annotations

import json
from abc import ABC
from abc import abstractmethod

import aio_pika
from pydantic import BaseModel
from src.logger_utils import get_logger
from src.models import Arbitrage
from src.models import Order
from src.models import PriceMessage
from src.models import TradeMessage
from src.strategies import TradingStrategy

logger = get_logger(__name__)


class EventObserver(ABC):
    @abstractmethod
    async def on_price_update(self, message: aio_pika.IncomingMessage):
        pass

    @abstractmethod
    async def on_trade_update(self, message: aio_pika.IncomingMessage):
        pass


class ArbitrageObserver(EventObserver, BaseModel):
    arbitrage: Arbitrage
    strategy: TradingStrategy
    channel: aio_pika.Channel | None = None
    connection: aio_pika.Connection | None = None
    amount_to_trade_usdt: float

    class Config:
        arbitrary_types_allowed = True

    async def connect(self, rabbitmq_url: str):
        self.connection = await aio_pika.connect_robust(rabbitmq_url)
        self.channel = await self.connection.channel()

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
            orders = self.strategy.generate_limit_orders(
                self.arbitrage, price, self.amount_to_trade_usdt
            )

            for order in orders:
                await self._publish_order(order)
        except Exception as e:
            logger.error("Error processing price update: %s", e)

        finally:
            await message.ack()

    async def on_trade_update(self, message: aio_pika.IncomingMessage):
        try:
            logger.info("Received trade update from %s", message.routing_key)
            trade_message = TradeMessage(**json.loads(message.body))
            orders = self.strategy.generate_market_orders(self.arbitrage, trade_message)

            for order in orders:
                await self._publish_order(order)
        except Exception as e:
            logger.error("Error processing trade update: %s", e)

        finally:
            await message.ack()

    async def subscribe(self):
        # Consume price updates from the origin exchange (kraken)
        price_subject = f"price_updates_{self.arbitrage.origin_exchange}"
        price_queue = await self.channel.declare_queue(price_subject)
        await price_queue.consume(self.on_price_update)

        # Consume trade updates from the target exchange (bitfinex)
        trade_subject = f"trade_updates_{self.arbitrage.target_exchange}"
        trade_queue = await self.channel.declare_queue(trade_subject)
        await trade_queue.consume(self.on_trade_update)
