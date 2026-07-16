from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.app import db
from backend.app.dao import order_dao, promotion_dao, stats_dao
from backend.app.main import normalize_book, page_slice, payload_int, require_address_fields
from backend.app.response import fail, http_exception_handler, ok


pytestmark = [pytest.mark.whitebox, pytest.mark.whitebox_unit]


@pytest.mark.parametrize(
    ("page", "size", "expected"),
    [(1, 2, [1, 2]), (2, 2, [3, 4]), (3, 2, [5]), (9, 2, []), (0, 2, [1, 2]), (-1, 2, [1, 2])],
)
def test_page_slice_paths(page, size, expected) -> None:
    assert page_slice([1, 2, 3, 4, 5], page, size) == expected


@pytest.mark.parametrize(
    ("payload", "default", "expected"),
    [({"value": 7}, None, 7), ({"value": " -8 "}, None, -8), ({}, 3, 3)],
)
def test_payload_int_valid_paths(payload, default, expected) -> None:
    assert payload_int(payload, "value", default=default) == expected


@pytest.mark.parametrize("value", [None, True, False, "1.2", "abc", {}, []])
def test_payload_int_invalid_paths(value) -> None:
    with pytest.raises(HTTPException) as caught:
        payload_int({"value": value}, "value")
    assert caught.value.status_code == 400


def test_address_required_fields_true_and_false_paths() -> None:
    require_address_fields({"receiverName": "A", "phone": "1", "detail": "Road"})
    for field in ("receiverName", "phone", "detail"):
        payload = {"receiverName": "A", "phone": "1", "detail": "Road"}
        payload[field] = " "
        with pytest.raises(HTTPException):
            require_address_fields(payload)
    with pytest.raises(HTTPException):
        require_address_fields({"receiverName": 1, "phone": "1", "detail": "Road"})


def test_normalize_book_all_default_and_conversion_paths() -> None:
    normalized = normalize_book(
        {"embedding": "secret", "cover": None, "publishDate": date(2026, 1, 2), "price": Decimal("9.5"), "originPrice": None, "stock": None, "salesCount": "2"}
    )
    assert "embedding" not in normalized
    assert normalized["publishDate"] == "2026-01-02"
    assert normalized["price"] == 9.5
    assert normalized["originPrice"] == 9.5
    assert normalized["stock"] == 0
    assert normalized["salesCount"] == 2


def test_response_envelope_and_exception_handler_paths() -> None:
    assert ok({"x": 1}) == {"code": 0, "message": "ok", "data": {"x": 1}}
    with pytest.raises(HTTPException) as caught:
        fail("bad", 409, 9)
    business = http_exception_handler(None, caught.value)
    plain = http_exception_handler(None, HTTPException(status_code=404, detail="missing"))
    assert business.status_code == 409 and b'"code":9' in business.body
    assert plain.status_code == 404 and b'"code":1' in plain.body


def test_database_row_conversion_and_result_set_paths(monkeypatch) -> None:
    cursor = MagicMock(description=[("amount",), ("name",)])
    assert db.row_to_dict(cursor, (Decimal("1.25"), "book")) == {"amount": 1.25, "name": "book"}
    cursor.fetchone.return_value = None
    assert db.one(cursor) is None
    cursor.fetchall.return_value = [(Decimal("2.5"), "a"), (Decimal("3.5"), "b")]
    assert db.many(cursor)[1]["amount"] == 3.5

    cursor.description = None
    cursor.nextset.side_effect = [True, False]
    monkeypatch.setattr(db, "one", lambda _: {"ok": True})
    cursor.execute.return_value = cursor
    cursor.description = [("ok",)]
    assert db.procedure_result(cursor, "sql") == {"ok": True}


def test_get_conn_commit_rollback_and_close_paths(monkeypatch) -> None:
    success = MagicMock()
    monkeypatch.setattr(db, "connect", lambda: success)
    with db.get_conn() as yielded:
        assert yielded is success
    success.commit.assert_called_once()
    success.close.assert_called_once()

    failure = MagicMock()
    monkeypatch.setattr(db, "connect", lambda: failure)
    with pytest.raises(RuntimeError):
        with db.get_conn():
            raise RuntimeError("boom")
    failure.rollback.assert_called_once()
    failure.close.assert_called_once()


@pytest.mark.parametrize(("method", "expected"), [("alipay", "支付宝"), ("wechat", "微信支付"), ("card", "银行卡"), ("cash", "cash"), (None, "支付宝")])
def test_payment_method_mapping_paths(method, expected) -> None:
    assert order_dao._payment_method_name(method) == expected


@pytest.mark.parametrize(("front", "store_id", "expected"), [("store", None, "店铺券"), (None, 3, "店铺券"), ("platform", None, "平台券")])
def test_coupon_type_condition_paths(front, store_id, expected) -> None:
    assert promotion_dao._db_coupon_type(front, store_id) == expected


@pytest.mark.parametrize(("value", "expected"), [("7d", 7), ("30d", 30), ("90d", 90), ("bad", 7), (None, 7)])
def test_statistics_range_mapping_paths(value, expected) -> None:
    assert stats_dao._days(value) == expected


def test_reward_amount_and_threshold_valid_invalid_paths() -> None:
    assert promotion_dao._reward_coupon_amount("ignored", 8) == 8
    assert promotion_dao._reward_coupon_amount("10元代金券") == 10
    assert promotion_dao._reward_coupon_min_amount(None) == 0
    for name, amount in (("no amount", None), ("ignored", 0), ("ignored", "bad")):
        with pytest.raises(ValueError):
            promotion_dao._reward_coupon_amount(name, amount)
    for value in (-1, "bad"):
        with pytest.raises(ValueError):
            promotion_dao._reward_coupon_min_amount(value)
