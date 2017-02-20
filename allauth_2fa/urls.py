from django.conf.urls import url

from allauth_2fa import views


urlpatterns = [
    url(r"^two-factor-authenticate/?$",
        views.TwoFactorAuthenticate.as_view(),
        name="two-factor-authenticate"),
    url(r"^two_factor/qr_code/?$",
        views.QRCodeGeneratorView.as_view(),
        name="two-factor-qr-code"),
]
