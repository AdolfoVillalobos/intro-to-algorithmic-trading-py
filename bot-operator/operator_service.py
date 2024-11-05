from __future__ import annotations

import asyncio

import aio_pika
from src.models import Arbitrage
from src.observer import ArbitrageObserver
from src.strategies import SimpleStrategy


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


if __name__ == "__main__":
    asyncio.run(main())
