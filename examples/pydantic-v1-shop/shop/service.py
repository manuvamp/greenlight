import json

from .models import Inventory, Order, Product, Settings


def load_product(raw: str) -> Product:
    return Product.parse_raw(raw)


def order_from_row(row) -> Order:
    return Order.from_orm(row)


def order_payload(order: Order) -> dict:
    return order.dict(by_alias=True, exclude={"created_at"})


def order_json(order: Order) -> str:
    return order.json(exclude={"created_at"})


def reprice(product: Product, new_price: int) -> Product:
    return product.copy(update={"price_cents": new_price})


def total_with_tax(order: Order, settings: Settings) -> int:
    return round(order.subtotal_cents() * (1 + settings.tax_rate))


def inventory_from_json(raw: str) -> Inventory:
    return Inventory.parse_obj(json.loads(raw))


def product_fields() -> list:
    return list(Product.__fields__.keys())


def product_schema_title() -> str:
    return Product.schema()["title"]
