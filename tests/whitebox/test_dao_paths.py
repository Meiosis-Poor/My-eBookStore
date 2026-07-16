from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pyodbc
import pytest

from backend.app.dao import order_dao, promotion_dao, review_dao


pytestmark = [pytest.mark.whitebox, pytest.mark.whitebox_dao]


@contextmanager
def connection_context(conn):
    yield conn


def configured_conn():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.execute.return_value = cursor
    conn.cursor.return_value = cursor
    return conn, cursor


def test_order_sequence_success_and_failure(monkeypatch) -> None:
    monkeypatch.setattr(order_dao, "procedure_result", lambda *args, **kwargs: {"newNo": "O1"})
    assert order_dao._next_no(MagicMock(), "order") == "O1"
    monkeypatch.setattr(order_dao, "procedure_result", lambda *args, **kwargs: None)
    with pytest.raises(ValueError):
        order_dao._next_no(MagicMock(), "order")


def test_order_procedure_error_known_and_fallback_paths() -> None:
    known = order_dao._procedure_error(pyodbc.Error("订单状态异常，无法支付"), "fallback")
    unknown = order_dao._procedure_error(pyodbc.Error("driver unavailable"), "fallback")
    assert "订单状态异常" in str(known)
    assert str(unknown) == "fallback"


def test_pay_order_not_found_invalid_and_idempotent_paths(monkeypatch) -> None:
    conn, _ = configured_conn()
    monkeypatch.setattr(order_dao, "get_conn", lambda: connection_context(conn))

    monkeypatch.setattr(order_dao, "one", lambda _: None)
    with pytest.raises(ValueError, match="订单不存在"):
        order_dao.pay(1, 2, "alipay")

    invalid = {"order_status": "已取消", "payment_status": "未支付"}
    monkeypatch.setattr(order_dao, "one", lambda _: invalid)
    with pytest.raises(ValueError, match="订单状态异常"):
        order_dao.pay(1, 2, "alipay")

    completed = {"order_status": "已完成", "payment_status": "已支付"}
    monkeypatch.setattr(order_dao, "one", lambda _: completed)
    monkeypatch.setattr(order_dao, "_payment_success", lambda connection, order: {"paymentStatus": "success", "idempotent": True})
    assert order_dao.pay(1, 2, "wechat")["idempotent"] is True


def test_pay_empty_items_stock_shortage_and_procedure_failure(monkeypatch) -> None:
    conn, _ = configured_conn()
    pending = {"order_status": "待支付", "payment_status": "未支付"}
    monkeypatch.setattr(order_dao, "get_conn", lambda: connection_context(conn))
    monkeypatch.setattr(order_dao, "one", lambda _: pending)

    monkeypatch.setattr(order_dao, "many", lambda _: [])
    with pytest.raises(ValueError, match="明细为空"):
        order_dao.pay(1, 2, "alipay")

    monkeypatch.setattr(order_dao, "many", lambda _: [{"stock": 0, "quantity": 1}])
    with pytest.raises(ValueError, match="库存不足"):
        order_dao.pay(1, 2, "alipay")

    monkeypatch.setattr(order_dao, "many", lambda _: [{"stock": 2, "quantity": 1}])
    monkeypatch.setattr(order_dao, "procedure_result", lambda *args, **kwargs: {"success": False})
    with pytest.raises(ValueError, match="支付失败"):
        order_dao.pay(1, 2, "alipay")


def test_pay_database_error_is_translated(monkeypatch) -> None:
    conn, _ = configured_conn()
    pending = {"order_status": "待支付", "payment_status": "未支付"}
    monkeypatch.setattr(order_dao, "get_conn", lambda: connection_context(conn))
    monkeypatch.setattr(order_dao, "one", lambda _: pending)
    monkeypatch.setattr(order_dao, "many", lambda _: [{"stock": 2, "quantity": 1}])
    monkeypatch.setattr(order_dao, "procedure_result", MagicMock(side_effect=pyodbc.Error("db")))
    with pytest.raises(ValueError, match="支付失败"):
        order_dao.pay(1, 2, "alipay")


@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_false_paths(rating) -> None:
    with pytest.raises(ValueError, match="评分"):
        review_dao.create(1, 2, 3, rating, "bad")


def test_review_purchase_payment_duplicate_and_success_paths(monkeypatch) -> None:
    conn, cursor = configured_conn()
    monkeypatch.setattr(review_dao, "get_conn", lambda: connection_context(conn))

    monkeypatch.setattr(review_dao, "one", lambda _: None)
    with pytest.raises(ValueError, match="已购买"):
        review_dao.create(1, 2, 3, 5, "x")

    monkeypatch.setattr(review_dao, "one", lambda _: {"payment_status": "未支付", "order_status": "待支付"})
    with pytest.raises(ValueError, match="支付完成"):
        review_dao.create(1, 2, 3, 5, "x")

    monkeypatch.setattr(review_dao, "one", lambda _: {"payment_status": "已支付", "order_status": "已完成"})
    cursor.fetchone.return_value = (1,)
    with pytest.raises(ValueError, match="已评价"):
        review_dao.create(1, 2, 3, 5, "x")

    cursor.fetchone.return_value = None
    review_dao.create(1, 2, 3, 1, "ok")
    assert cursor.execute.call_count >= 3


def test_reward_type_and_procedure_error_paths() -> None:
    assert promotion_dao._db_reward_type("physical") == "实物"
    assert promotion_dao._db_reward_type("coupon") == "代金券"
    with pytest.raises(ValueError):
        promotion_dao._db_reward_type("unknown")
    assert "积分不足" in str(promotion_dao._procedure_error(pyodbc.Error("积分不足"), "fallback"))
    assert str(promotion_dao._procedure_error(pyodbc.Error("db"), "fallback")) == "fallback"
