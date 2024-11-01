from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import aio_pika
from pydantic import BaseModel
from pydantic import Field
from src.logger_utils import get_logger
from src.models import Arbitrage
from src.models import Order
from src.models import PriceMessage
from src.models import TradeMessage

logger = get_logger(__name__)

Balance = dict[str, float]
StrategyFn = Callable[[Arbitrage, PriceMessage, Balance], list[Order]]


def simple_strategy(
    arbitrage: Arbitrage, price: PriceMessage, balances: Balance
) -> list[Order]:
    ask_price = price.ask_price * (1.0 + arbitrage.markup())
    bid_price = price.bid_price * (1.0 - arbitrage.markup())

    ask_quantity = balances["BTC"]
    bid_quantity = balances["USDT"] / ask_price
    return [
        Order(
            symbol=arbitrage.target_market,
            quantity=bid_quantity,
            price=bid_price,
            side="buy",
            exchange=arbitrage.target_exchange,
            order_type="limit",
        ),
        Order(
            symbol=arbitrage.target_market,
            quantity=ask_quantity,
            price=ask_price,
            side="sell",
            exchange=arbitrage.target_exchange,
            order_type="limit",
        ),
    ]


class Observer(BaseModel):
    arbitrage: Arbitrage
    strategy: StrategyFn
    channel: aio_pika.Channel | None = None
    balances: Balance = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def target_exchange(self) -> str:
        return self.arbitrage.target_exchange

    def origin_exchange(self) -> str:
        return self.arbitrage.origin_exchange

    async def on_price_update(self, message: aio_pika.IncomingMessage):
        try:
            logger.info("Received price update from %s", message.routing_key)
            price = PriceMessage(**json.loads(message.body))
            orders = self.strategy(self.arbitrage, price, self.balances)

            for order in orders:
                subject = order.subject()
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=order.model_dump_json().encode()),
                    routing_key=subject,
                )
                logger.info("New decision to %s: %s", subject, order)
        except Exception as e:
            logger.error("Error processing price update: %s", e)

        finally:
            await message.ack()

    async def on_trade_update(self, message: aio_pika.IncomingMessage):
        try:
            logger.info("Received trade update from %s", message.routing_key)
            trade = TradeMessage(**json.loads(message.body))
            order = self.arbitrage.complete_arbitrage(trade)
            if order:
                subject = order.subject()
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=order.model_dump_json().encode()),
                    routing_key=subject,
                )
                logger.info("New decision to %s: %s", subject, order)
        except Exception as e:
            logger.error("Error processing trade update: %s", e)

        finally:
            await message.ack()

    async def subscribe(self, connection: aio_pika.Connection):
        self.channel = await connection.channel()

        # Declare price updates queue
        queue_price_updates = await self.channel.declare_queue(
            f"price_updates_{self.origin_exchange()}"
        )
        await queue_price_updates.consume(self.on_price_update)

        # Declare limit updates queue
        _ = await self.channel.declare_queue(f"limit_updates_{self.target_exchange()}")

        # Declare taker updates queue
        queue_trades_updates = await self.channel.declare_queue(
            f"trades_updates_{self.target_exchange()}"
        )
        await queue_trades_updates.consume(self.on_trade_update)

        await asyncio.Future()


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
    observer = Observer(
        arbitrage=arbitrage,
        strategy=simple_strategy,
        balances={"BTC": 0.0, "USDT": 100.0},
    )
    await observer.subscribe(connection)


if __name__ == "__main__":
    asyncio.run(main())
