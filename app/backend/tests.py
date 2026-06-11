from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from backend.models import ConfirmEmailToken, Contact, Order, ProductInfo, Shop
from backend.services import import_price_list


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class ImportPriceListTests(TestCase):
    def test_imports_shop_catalog_from_yaml(self):
        result = import_price_list(DATA_DIR / "shop1.yaml")

        self.assertEqual(result.created_products, 14)
        self.assertEqual(Shop.objects.get().name, "Связной")
        self.assertEqual(ProductInfo.objects.count(), 14)
        self.assertTrue(
            ProductInfo.objects.filter(
                product__name__icontains="iPhone XS Max",
                product_parameters__parameter__name="Цвет",
                product_parameters__value="золотистый",
            ).exists()
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class CustomerFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        import_price_list(DATA_DIR / "shop1.yaml")

    def test_registration_confirmation_login_and_order_flow(self):
        register = self.client.post(
            "/api/v1/user/register",
            {
                "first_name": "Ivan",
                "last_name": "Petrov",
                "email": "ivan@example.com",
                "password": "StrongPass123",
            },
            format="json",
        )
        self.assertEqual(register.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)

        token = ConfirmEmailToken.objects.get(user__email="ivan@example.com")
        confirm = self.client.post(
            "/api/v1/user/register/confirm",
            {"email": "ivan@example.com", "token": token.key},
            format="json",
        )
        self.assertEqual(confirm.status_code, 200)

        login = self.client.post(
            "/api/v1/user/login",
            {"email": "ivan@example.com", "password": "StrongPass123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['Token']}")

        product_info = ProductInfo.objects.first()
        basket = self.client.post(
            "/api/v1/basket",
            {"items": [{"product_info": product_info.id, "quantity": 2}]},
            format="json",
        )
        self.assertEqual(basket.status_code, 200)

        contact = self.client.post(
            "/api/v1/user/contact",
            {
                "city": "Moscow",
                "street": "Tverskaya",
                "house": "1",
                "phone": "+79990000000",
            },
            format="json",
        )
        self.assertEqual(contact.status_code, 201)
        contact_id = Contact.objects.get(user__email="ivan@example.com").id

        basket_id = Order.objects.get(user__email="ivan@example.com", state=Order.State.BASKET).id
        order = self.client.post(
            "/api/v1/order",
            {"id": basket_id, "contact": contact_id},
            format="json",
        )
        self.assertEqual(order.status_code, 200)
        self.assertEqual(len(mail.outbox), 3)

        orders = self.client.get("/api/v1/order")
        self.assertEqual(orders.status_code, 200)
        self.assertEqual(orders.data[0]["state"], Order.State.NEW)

    def test_basket_update_validates_quantity(self):
        user = get_user_model().objects.create_user(
            email="buyer@example.com",
            password="StrongPass123",
            is_active=True,
        )
        token = Token.objects.create(user=user)
        product_info = ProductInfo.objects.first()
        order = Order.objects.create(user=user, state=Order.State.BASKET)
        item = order.ordered_items.create(product_info=product_info, quantity=2)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.put(
            "/api/v1/basket",
            {"items": [{"id": item.id, "quantity": None}]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)


class ThrottlingTests(TestCase):
    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_registration_is_throttled(self):
        cache.clear()
        client = APIClient()

        for index in range(5):
            response = client.post(
                "/api/v1/user/register",
                {
                    "first_name": "Ivan",
                    "last_name": "Petrov",
                    "email": f"ivan{index}@example.com",
                    "password": "StrongPass123",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)

        response = client.post(
            "/api/v1/user/register",
            {
                "first_name": "Ivan",
                "last_name": "Petrov",
                "email": "ivan5@example.com",
                "password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 429)


class PartnerFlowTests(TestCase):
    def test_shop_can_toggle_state(self):
        user = get_user_model().objects.create_user(
            email="shop@example.com",
            password="StrongPass123",
            type=get_user_model().Type.SHOP,
            is_active=True,
        )
        Shop.objects.create(name="Partner", user=user)
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post("/api/v1/partner/state", {"state": False}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Shop.objects.get(user=user).state)
