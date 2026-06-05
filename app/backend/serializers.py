from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from backend.models import Contact, Order, OrderItem, ProductInfo, ProductParameter, Shop


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password", "company", "position")
        extra_kwargs = {
            "company": {"required": False},
            "position": {"required": False},
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, is_active=False, **validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "company", "position", "type")
        read_only_fields = ("id", "email", "type")


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ("id", "city", "street", "house", "structure", "building", "apartment", "phone")
        read_only_fields = ("id",)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ("id", "name", "state")


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.CharField(source="parameter.name")

    class Meta:
        model = ProductParameter
        fields = ("parameter", "value")


class ProductInfoSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="product.name")
    category = serializers.CharField(source="product.category.name")
    shop = ShopSerializer()
    parameters = ProductParameterSerializer(source="product_parameters", many=True)

    class Meta:
        model = ProductInfo
        fields = (
            "id",
            "external_id",
            "model",
            "name",
            "category",
            "shop",
            "quantity",
            "price",
            "price_rrc",
            "parameters",
        )


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductInfoSerializer(source="product_info", read_only=True)
    sum = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ("id", "product_info", "product", "quantity", "sum")
        extra_kwargs = {"product_info": {"write_only": True}}

    def get_sum(self, obj):
        return obj.quantity * obj.product_info.price


class OrderSerializer(serializers.ModelSerializer):
    ordered_items = OrderItemSerializer(many=True, read_only=True)
    total_sum = serializers.IntegerField(read_only=True)
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ("id", "dt", "state", "contact", "ordered_items", "total_sum")
