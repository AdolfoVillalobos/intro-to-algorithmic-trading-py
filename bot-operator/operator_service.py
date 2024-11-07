from __future__ import annotations

import asyncio

from src.models import Arbitrage
from src.observer import ArbitrageObserver
from src.strategies import SimpleStrategy


async def operator_service():
    arbitrage = Arbitrage(
        target_market="BTC/USDT",
        origin_market="BTC/USDT",
        target_exchange="bitfinex",
        origin_exchange="kraken",
        profit_threshold=0.01,
        target_fee=0.002,
        origin_fee=0.001,
    )

    observer = ArbitrageObserver(
        arbitrage=arbitrage,
        strategy=SimpleStrategy(),
        amount_to_trade_usdt=15.0,
    )
    await observer.connect("amqp://guest:guest@rabbitmq/")
    await observer.subscribe()


if __name__ == "__main__":
    asyncio.run(operator_service())
