import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from shop.models import Inventory, LineItem, Order, Product, Settings
from shop import service

P = {"sku": "ABC-1234", "name": "  Lamp  ", "price_cents": 2500, "tags": ["Home", "LIGHT"]}


def make_order(**kw):
    return Order(id=1, items=[LineItem(product=Product(**P), quantity=2)], **kw)


def test_product_strips_and_lowercases():
    p = Product(**P)
    assert p.name == "Lamp"
    assert p.tags == ["home", "light"]
    assert p.discontinued is None


def test_sku_pattern_enforced():
    with pytest.raises(ValidationError):
        Product(**{**P, "sku": "bad"})


def test_product_is_immutable():
    p = Product(**P)
    with pytest.raises((TypeError, ValidationError)):
        p.name = "x"


def test_reprice_returns_copy():
    p = Product(**P)
    q = service.reprice(p, 999)
    assert q.price_cents == 999 and p.price_cents == 2500


def test_load_product_from_json():
    assert service.load_product(json.dumps(P)).sku == "ABC-1234"


def test_order_subtotal_and_tax():
    o = make_order()
    assert o.subtotal_cents() == 5000
    assert service.total_with_tax(o, Settings()) == 5900


def test_empty_order_rejected():
    with pytest.raises(ValidationError):
        Order(id=2, items=[])


def test_order_alias_round_trip():
    o = Order(id=3, items=make_order().items, couponCode="SAVE10")
    assert o.coupon == "SAVE10"
    assert service.order_payload(o)["couponCode"] == "SAVE10"
    assert json.loads(service.order_json(o))["coupon"] == "SAVE10"


def test_order_kind_is_constant():
    with pytest.raises(ValidationError):
        make_order(kind="refund")


def test_order_from_orm_row():
    row = SimpleNamespace(id=7, items=make_order().items, coupon=None, kind="order",
                          created_at=make_order().created_at)
    assert service.order_from_row(row).id == 7


def test_inventory_root_model():
    inv = service.inventory_from_json('{"ABC-1234": 3}')
    assert inv.count("ABC-1234") == 3
    assert inv.count("ZZZ-0000") == 0


def test_settings_env(monkeypatch):
    monkeypatch.setenv("SHOP_TAX_RATE", "0.05")
    assert Settings().tax_rate == 0.05


def test_introspection():
    assert service.product_fields()[:2] == ["sku", "name"]
    assert service.product_schema_title() == "Product"
