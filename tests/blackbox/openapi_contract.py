from __future__ import annotations

from copy import deepcopy
from typing import Any

import schemathesis

from backend.app.main import app


OBJECT_SCHEMAS: dict[tuple[str, str], dict[str, Any]] = {
    ("/api/auth/register/user", "post"): {
        "required": ["userName", "password"],
        "properties": {
            "userName": {"type": "string", "minLength": 3, "maxLength": 50},
            "password": {"type": "string", "minLength": 6, "maxLength": 100},
            "nickname": {"type": "string", "maxLength": 50},
            "phone": {"type": "string", "maxLength": 20},
            "email": {"type": "string", "maxLength": 100},
        },
    },
    ("/api/auth/login", "post"): {
        "required": ["userName", "password", "role"],
        "properties": {
            "userName": {"type": "string", "minLength": 1},
            "password": {"type": "string", "minLength": 1},
            "role": {"type": "string", "enum": ["customer", "seller", "platform_admin"]},
        },
    },
    ("/api/cart", "post"): {
        "required": ["bookItemId", "quantity"],
        "properties": {
            "bookItemId": {"type": "integer", "minimum": 1},
            "quantity": {"type": "integer", "minimum": 1},
        },
    },
    ("/api/addresses", "post"): {
        "required": ["receiverName", "phone", "detail"],
        "properties": {
            "receiverName": {"type": "string", "minLength": 1, "maxLength": 50},
            "phone": {"type": "string", "minLength": 1, "maxLength": 20},
            "detail": {"type": "string", "minLength": 1, "maxLength": 200},
            "isDefault": {"type": "boolean"},
        },
    },
    ("/api/orders", "post"): {
        "required": ["cartItemIds", "addressId"],
        "properties": {
            "cartItemIds": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1},
                "minItems": 1,
                "uniqueItems": True,
            },
            "addressId": {"type": "integer", "minimum": 1},
            "couponId": {"type": ["integer", "null"], "minimum": 1},
        },
    },
}


def _object_schema(definition: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, **definition}


def build_schema():
    original = app.openapi_schema
    raw = deepcopy(app.openapi())
    for (path, method), definition in OBJECT_SCHEMAS.items():
        operation = raw["paths"][path][method]
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": _object_schema(definition)}},
        }
    app.openapi_schema = raw
    try:
        return schemathesis.openapi.from_asgi("/openapi.json", app)
    finally:
        app.openapi_schema = original


schema = build_schema()
