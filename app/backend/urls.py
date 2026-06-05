from django.urls import path

from backend.views import (
    AccountDetails,
    BasketView,
    ConfirmAccount,
    ContactView,
    LoginAccount,
    OrderView,
    PartnerOrders,
    PartnerState,
    PartnerUpdate,
    ProductInfoView,
    RegisterAccount,
)


urlpatterns = [
    path("partner/update", PartnerUpdate.as_view(), name="partner-update"),
    path("partner/state", PartnerState.as_view(), name="partner-state"),
    path("partner/orders", PartnerOrders.as_view(), name="partner-orders"),
    path("user/register", RegisterAccount.as_view(), name="user-register"),
    path("user/register/confirm", ConfirmAccount.as_view(), name="user-register-confirm"),
    path("user/login", LoginAccount.as_view(), name="user-login"),
    path("user/details", AccountDetails.as_view(), name="user-details"),
    path("user/contact", ContactView.as_view(), name="user-contact"),
    path("products", ProductInfoView.as_view(), name="products"),
    path("basket", BasketView.as_view(), name="basket"),
    path("order", OrderView.as_view(), name="order"),
]
