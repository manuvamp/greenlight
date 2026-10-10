from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, BaseSettings, Field, root_validator, validator


class Settings(BaseSettings):
    currency: str = "USD"
    tax_rate: float = 0.18

    class Config:
        env_prefix = "SHOP_"


class Product(BaseModel):
    sku: str = Field(..., regex=r"^[A-Z]{3}-\d{4}$")
    name: str
    price_cents: int = Field(..., gt=0)
    tags: List[str] = []
    discontinued: Optional[bool]

    class Config:
        anystr_strip_whitespace = True
        allow_mutation = False

    @validator("tags", each_item=True)
    def lower_tags(cls, v):
        return v.lower()


class LineItem(BaseModel):
    product: Product
    quantity: int = Field(1, ge=1)

    @property
    def total_cents(self) -> int:
        return self.product.price_cents * self.quantity


class Order(BaseModel):
    kind: str = Field("order", const=True)
    id: int
    items: List[LineItem]
    coupon: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        fields = {"coupon": {"alias": "couponCode"}}

    @root_validator
    def no_empty_orders(cls, values):
        if not values.get("items"):
            raise ValueError("an order needs at least one item")
        return values

    def subtotal_cents(self) -> int:
        return sum(i.total_cents for i in self.items)


class Inventory(BaseModel):
    __root__: Dict[str, int]

    def count(self, sku: str) -> int:
        return self.__root__.get(sku, 0)
