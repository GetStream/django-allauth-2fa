from django.conf.urls import url

from . import views


urlpatterns =  [
    url(r"^two-factor-authenticate$",
        views.two_factor_authenticate,
        name="two-factor-authenticate"),

    url(r"^two_factor/qr_code$",
        views.two_factor_qr_code_generator,
        name="two-factor-qr-code"),
]
