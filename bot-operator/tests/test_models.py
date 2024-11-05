from __future__ import annotations

from datetime import datetime

import pytest
from src.models import Arbitrage
from src.models import Order
from src.models import TradeMessage


@pytest.fixture
def arbitrage():
    return Arbitrage(
        target_market="BTC/USDT",
        origin_market="BTC/USDT",
        target_exchange="bitfinex",
        origin_exchange="kraken",
        profit_threshold=0.05,
        target_fee=0.002,
        origin_fee=0.001,
    )


def test_arbitrage_markup(arbitrage):
    assert arbitrage.markup() == pytest.approx(0.053)


def test_complete_arbitrage(arbitrage):
    trade_message = TradeMessage(
        symbol="BTC/USDT",
        amount=1,
        side="sell",
        price=65_000,
        exchange="bitfinex",
        datetime=datetime.now(),
    )

    new_order = arbitrage.complete_arbitrage(trade_message)
    assert isinstance(new_order, Order)
    assert new_order.symbol == "BTC/USDT"
    assert new_order.quantity == 1.0
    assert new_order.side == "buy"
    assert new_order.price is None
    assert new_order.exchange == "kraken"
    assert new_order.order_type == "market"

    assert new_order.subject() == "order_updates_kraken"


def test_complete_arbitrage_wrong_exchange(arbitrage):
    trade_message = TradeMessage(
        symbol="BTC/USDT",
        amount=1,
        side="sell",
        price=65_000,
        exchange="binance",
        datetime=datetime.now(),
    )

    order = arbitrage.complete_arbitrage(trade_message)
    assert order is None
