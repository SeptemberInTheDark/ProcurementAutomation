from urllib.request import urlopen

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.models import ConfirmEmailToken, Contact, Order, OrderItem, ProductInfo
from backend.serializers import (
    ConfirmAccountSerializer,
    ContactSerializer,
    LoginSerializer,
    OrderItemSerializer,
    OrderSerializer,
    PartnerStateSerializer,
    PartnerUpdateSerializer,
    ProductInfoSerializer,
    RegisterSerializer,
    ShopSerializer,
    UserSerializer,
)
from backend.services import import_price_list, send_confirmation_email, send_order_emails


def parse_bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError("Invalid boolean value")


class RegisterAccount(generics.GenericAPIView):
    """Register a buyer account and send an email confirmation token."""

    serializer_class = RegisterSerializer
    throttle_scope = "user_register"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = ConfirmEmailToken.objects.create(user=user)
        send_confirmation_email(user, token)
        return Response({"Status": True}, status=status.HTTP_201_CREATED)


class ConfirmAccount(generics.GenericAPIView):
    """Confirm a registered account using the token sent by email."""

    serializer_class = ConfirmAccountSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = ConfirmEmailToken.objects.filter(
            user__email=serializer.validated_data["email"],
            key=serializer.validated_data["token"],
        ).select_related("user").first()
        if not token:
            return Response({"Status": False, "Errors": "Invalid token or email"}, status=400)
        token.user.is_active = True
        token.user.save(update_fields=["is_active"])
        token.delete()
        return Response({"Status": True})


class LoginAccount(generics.GenericAPIView):
    """Authenticate an active user and return a DRF token."""

    serializer_class = LoginSerializer
    throttle_scope = "user_login"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if not user or not user.is_active:
            return Response({"Status": False, "Errors": "Invalid credentials"}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"Status": True, "Token": token.key})


class AccountDetails(generics.GenericAPIView):
    """Read or update current user profile details."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        return Response(self.get_serializer(request.user).data)

    def post(self, request):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"Status": True})


class ProductInfoView(generics.ListAPIView):
    """List products from active shops with optional shop, category, and search filters."""

    serializer_class = ProductInfoSerializer

    def get_queryset(self):
        query = Q(shop__state=True)
        if shop_id := self.request.query_params.get("shop_id"):
            query &= Q(shop_id=shop_id)
        if category_id := self.request.query_params.get("category_id"):
            query &= Q(product__category_id=category_id)
        if search := self.request.query_params.get("search"):
            query &= Q(product__name__icontains=search)
        return (
            ProductInfo.objects.filter(query)
            .select_related("shop", "product", "product__category")
            .prefetch_related("product_parameters__parameter")
        )


class BasketView(generics.GenericAPIView):
    """Read, add, update, and delete items in the current user's basket."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get(self, request):
        basket = self._get_basket(request.user)
        return Response(OrderSerializer(basket).data)

    @transaction.atomic
    def post(self, request):
        basket = self._get_basket(request.user)
        items = self._parse_items(request.data.get("items", request.data))
        created = 0
        for item in items:
            serializer = OrderItemSerializer(data=item)
            serializer.is_valid(raise_exception=True)
            order_item, is_created = OrderItem.objects.update_or_create(
                order=basket,
                product_info=serializer.validated_data["product_info"],
                defaults={"quantity": serializer.validated_data["quantity"]},
            )
            created += int(is_created)
        return Response({"Status": True, "Created": created})

    def put(self, request):
        basket = self._get_basket(request.user)
        items = self._parse_items(request.data.get("items", []))
        if not isinstance(items, list):
            return Response({"Status": False, "Errors": "Invalid items"}, status=400)

        updated = 0
        for item in items:
            if not isinstance(item, dict):
                return Response({"Status": False, "Errors": "Invalid item"}, status=400)

            order_item = OrderItem.objects.filter(order=basket, id=item.get("id")).first()
            if not order_item or "quantity" not in item:
                return Response({"Status": False, "Errors": "Invalid item"}, status=400)

            serializer = OrderItemSerializer(order_item, data={"quantity": item["quantity"]}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            updated += 1
        return Response({"Status": True, "Updated": updated})

    def delete(self, request):
        basket = self._get_basket(request.user)
        ids = request.data.get("items", [])
        if isinstance(ids, str):
            ids = [item for item in ids.split(",") if item]
        deleted, _ = OrderItem.objects.filter(order=basket, id__in=ids).delete()
        return Response({"Status": True, "Deleted": deleted})

    @staticmethod
    def _get_basket(user):
        basket, _ = Order.objects.get_or_create(user=user, state=Order.State.BASKET)
        return (
            Order.objects.filter(pk=basket.pk)
            .prefetch_related(
                "ordered_items__product_info__shop",
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .get()
        )

    @staticmethod
    def _parse_items(items):
        if isinstance(items, dict):
            return [items]
        return items


class ContactView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def delete(self, request):
        ids = request.data.get("items", [])
        if isinstance(ids, str):
            ids = [item for item in ids.split(",") if item]
        deleted, _ = self.get_queryset().filter(id__in=ids).delete()
        return Response({"Status": True, "Deleted": deleted})


class OrderView(generics.GenericAPIView):
    """List submitted orders and turn a basket into a new order."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get(self, request):
        orders = (
            Order.objects.filter(user=request.user)
            .exclude(state=Order.State.BASKET)
            .select_related("contact")
            .prefetch_related(
                "ordered_items__product_info__shop",
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
        )
        return Response(OrderSerializer(orders, many=True).data)

    @transaction.atomic
    def post(self, request):
        order = Order.objects.filter(
            user=request.user,
            id=request.data.get("id"),
            state=Order.State.BASKET,
        ).first()
        contact = Contact.objects.filter(user=request.user, id=request.data.get("contact")).first()
        if not order or not contact or not order.ordered_items.exists():
            return Response({"Status": False, "Errors": "Invalid basket or contact"}, status=400)
        order.contact = contact
        order.state = Order.State.NEW
        order.save(update_fields=["contact", "state"])
        send_order_emails(order)
        return Response({"Status": True})


class PartnerUpdate(generics.GenericAPIView):
    """Import a partner price list from an uploaded YAML file or remote URL."""

    permission_classes = [IsAuthenticated]
    serializer_class = PartnerUpdateSerializer
    throttle_scope = "partner_update"

    def post(self, request):
        if request.user.type != request.user.Type.SHOP:
            return Response({"Status": False, "Error": "Only shops can import price lists"}, status=403)

        uploaded_file = request.FILES.get("file")
        url = request.data.get("url")
        if uploaded_file:
            result = import_price_list(uploaded_file, user=request.user)
        elif url:
            with urlopen(url, timeout=10) as response:
                result = import_price_list(response, user=request.user)
        else:
            return Response({"Status": False, "Errors": "File or url is required"}, status=400)

        return Response({"Status": True, "Imported": result.created_products})


class PartnerState(generics.GenericAPIView):
    """Read or update current partner shop availability."""

    permission_classes = [IsAuthenticated]
    serializer_class = PartnerStateSerializer

    def get(self, request):
        if request.user.type != request.user.Type.SHOP:
            return Response({"Status": False, "Error": "Only shops can manage state"}, status=403)
        return Response(ShopSerializer(request.user.shop).data)

    def post(self, request):
        if request.user.type != request.user.Type.SHOP:
            return Response({"Status": False, "Error": "Only shops can manage state"}, status=403)
        try:
            request.user.shop.state = parse_bool(request.data.get("state"))
        except ValueError as error:
            return Response({"Status": False, "Errors": str(error)}, status=400)
        request.user.shop.save(update_fields=["state"])
        return Response({"Status": True})


class PartnerOrders(generics.GenericAPIView):
    """List non-basket orders that include current partner products."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get(self, request):
        if request.user.type != request.user.Type.SHOP:
            return Response({"Status": False, "Error": "Only shops can see partner orders"}, status=403)
        orders = (
            Order.objects.filter(ordered_items__product_info__shop__user=request.user)
            .exclude(state=Order.State.BASKET)
            .select_related("contact")
            .prefetch_related("ordered_items__product_info__product__category")
            .distinct()
        )
        return Response(OrderSerializer(orders, many=True).data)
