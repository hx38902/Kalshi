"""Unit tests for data models."""

from kalshi_client.models import Market, Event, Balance, Position, OrderBook, Fill


def test_market_from_api():
    data = {
        "ticker": "TEST-MARKET",
        "event_ticker": "TEST-EVENT",
        "title": "Test Market",
        "status": "open",
        "yes_bid": 45,
        "yes_ask": 55,
        "no_bid": 45,
        "no_ask": 55,
        "volume": 1000,
        "open_interest": 500,
        "last_price": 50,
    }
    m = Market.from_api(data)
    assert m.ticker == "TEST-MARKET"
    assert m.yes_bid == 0.45
    assert m.yes_ask == 0.55
    assert m.volume == 1000
    assert m.last_price == 0.50


def test_market_zero_prices():
    data = {"ticker": "T", "event_ticker": "E", "title": "T", "status": "open"}
    m = Market.from_api(data)
    assert m.yes_bid == 0.0
    assert m.yes_ask == 0.0


def test_event_from_api():
    data = {
        "event_ticker": "TEST-EVENT",
        "title": "Test Event",
        "category": "politics",
        "status": "open",
        "markets": ["m1", "m2"],
    }
    e = Event.from_api(data)
    assert e.event_ticker == "TEST-EVENT"
    assert e.category == "politics"
    assert len(e.markets) == 2


def test_balance_from_api():
    data = {"balance": 10050, "payout": 500}
    b = Balance.from_api(data)
    assert b.balance == 10050
    assert b.balance_dollars == 100.50
    assert b.payout == 500


def test_position_from_api():
    data = {
        "ticker": "POS-MARKET",
        "market_exposure": 200,
        "resting_orders_count": 3,
        "total_traded": 500,
        "realized_pnl": -50,
        "fees_paid": 10,
    }
    p = Position.from_api(data)
    assert p.ticker == "POS-MARKET"
    assert p.market_exposure == 200
    assert p.realized_pnl == -50


def test_orderbook_from_api():
    data = {
        "yes": {"bids": [{"price": 40, "count": 10}], "asks": [{"price": 60, "count": 5}]},
        "no": {"bids": [{"price": 40, "count": 8}], "asks": []},
    }
    ob = OrderBook.from_api("TEST", data)
    assert ob.ticker == "TEST"
    assert len(ob.yes_bids) == 1
    assert len(ob.yes_asks) == 1
    assert len(ob.no_bids) == 1
    assert len(ob.no_asks) == 0


def test_fill_from_api():
    data = {
        "trade_id": "abc123",
        "ticker": "FILL-MARKET",
        "side": "yes",
        "action": "buy",
        "count": 5,
        "yes_price": 60,
        "no_price": 40,
        "created_time": "2026-01-01T00:00:00Z",
    }
    f = Fill.from_api(data)
    assert f.trade_id == "abc123"
    assert f.side == "yes"
    assert f.count == 5
