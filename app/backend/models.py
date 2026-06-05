from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django_rest_passwordreset.tokens import get_token_generator


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Type(models.TextChoices):
        BUYER = "buyer", "Buyer"
        SHOP = "shop", "Shop"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    company = models.CharField(max_length=80, blank=True)
    position = models.CharField(max_length=80, blank=True)
    type = models.CharField(max_length=5, choices=Type.choices, default=Type.BUYER)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email


class Shop(models.Model):
    name = models.CharField(max_length=80, unique=True)
    url = models.URLField(blank=True)
    user = models.OneToOneField(User, related_name="shop", null=True, blank=True, on_delete=models.CASCADE)
    state = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=80)
    shops = models.ManyToManyField(Shop, related_name="categories", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=160)
    category = models.ForeignKey(Category, related_name="products", on_delete=models.CASCADE)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "category"], name="unique_product_in_category"),
        ]

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    external_id = models.PositiveBigIntegerField()
    model = models.CharField(max_length=120, blank=True)
    product = models.ForeignKey(Product, related_name="product_infos", on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, related_name="product_infos", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    price = models.PositiveIntegerField()
    price_rrc = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shop", "external_id"], name="unique_external_product_per_shop"),
        ]

    def __str__(self):
        return f"{self.product} / {self.shop}"


class Parameter(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, related_name="product_parameters", on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, related_name="product_parameters", on_delete=models.CASCADE)
    value = models.CharField(max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product_info", "parameter"], name="unique_product_parameter"),
        ]


class Contact(models.Model):
    user = models.ForeignKey(User, related_name="contacts", on_delete=models.CASCADE)
    city = models.CharField(max_length=80)
    street = models.CharField(max_length=120)
    house = models.CharField(max_length=20, blank=True)
    structure = models.CharField(max_length=20, blank=True)
    building = models.CharField(max_length=20, blank=True)
    apartment = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.city}, {self.street}"


class Order(models.Model):
    class State(models.TextChoices):
        BASKET = "basket", "Basket"
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        ASSEMBLED = "assembled", "Assembled"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        CANCELED = "canceled", "Canceled"

    user = models.ForeignKey(User, related_name="orders", on_delete=models.CASCADE)
    dt = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=15, choices=State.choices, default=State.BASKET)
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-dt"]

    @property
    def total_sum(self):
        return sum(item.quantity * item.product_info.price for item in self.ordered_items.all())

    def __str__(self):
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="ordered_items", on_delete=models.CASCADE)
    product_info = models.ForeignKey(ProductInfo, related_name="ordered_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product_info"], name="unique_order_item"),
        ]


class ConfirmEmailToken(models.Model):
    user = models.ForeignKey(User, related_name="confirm_email_tokens", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    key = models.CharField(max_length=64, unique=True, db_index=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = get_token_generator().generate_token()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Email confirmation token for {self.user_id}"
