from dataclasses import dataclass
from pathlib import Path

import yaml
from django.db import transaction

from backend.models import Category, Parameter, Product, ProductInfo, ProductParameter, Shop
from backend.tasks import send_confirmation_email_task, send_order_emails_task


@dataclass(frozen=True)
class ImportResult:
    shop: Shop
    created_products: int


@transaction.atomic
def import_price_list(source, *, user=None) -> ImportResult:
    if hasattr(source, "read"):
        data = yaml.safe_load(source)
    else:
        data = yaml.safe_load(Path(source).read_text(encoding="utf-8"))

    shop, _ = Shop.objects.update_or_create(
        name=data["shop"],
        defaults={"user": user, "url": getattr(source, "name", "")[:200]} if user else {},
    )

    for item in data.get("categories", []):
        category, _ = Category.objects.update_or_create(
            id=item["id"],
            defaults={"name": item["name"]},
        )
        category.shops.add(shop)

    ProductInfo.objects.filter(shop=shop).delete()
    created = 0
    for item in data.get("goods", []):
        category = Category.objects.get(id=item["category"])
        product, _ = Product.objects.get_or_create(name=item["name"], category=category)
        product_info = ProductInfo.objects.create(
            external_id=item["id"],
            model=item.get("model", ""),
            product=product,
            shop=shop,
            quantity=item["quantity"],
            price=item["price"],
            price_rrc=item["price_rrc"],
        )
        for name, value in item.get("parameters", {}).items():
            parameter, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.create(
                product_info=product_info,
                parameter=parameter,
                value=str(value),
            )
        created += 1

    return ImportResult(shop=shop, created_products=created)


def send_confirmation_email(user, token):
    send_confirmation_email_task.delay(user.email, token.key)


def send_order_emails(order):
    send_order_emails_task.delay(order.id)
