from django.contrib import admin
from django.urls import include, path
from django_rest_passwordreset.views import reset_password_confirm, reset_password_request_token
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("backend.urls")),
    path("api/v1/user/password_reset", reset_password_request_token, name="password-reset"),
    path("api/v1/user/password_reset/confirm", reset_password_confirm, name="password-reset-confirm"),
]
