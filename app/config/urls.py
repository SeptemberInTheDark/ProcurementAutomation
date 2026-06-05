from django.contrib import admin
from django.urls import include, path
from django_rest_passwordreset.views import reset_password_confirm, reset_password_request_token


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("backend.urls")),
    path("api/v1/user/password_reset", reset_password_request_token, name="password-reset"),
    path("api/v1/user/password_reset/confirm", reset_password_confirm, name="password-reset-confirm"),
]
