from base64 import b32encode
from binascii import unhexlify
try:
    from urllib.parse import quote, urlencode
except ImportError:
    from urllib import quote, urlencode

from django.core.urlresolvers import reverse_lazy
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
# from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect
from django.views.generic import FormView, View, TemplateView

from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

import qrcode
from qrcode.image.svg import SvgPathImage

from allauth_2fa.forms import (TOTPDeviceForm,
                               TOTPDeviceRemoveForm,
                               TOTPAuthenticateForm)


if hasattr(settings, 'LOGIN_REDIRECT_URL'):
    SUCCESS_URL = settings.LOGIN_REDIRECT_URL
else:
    SUCCESS_URL = reverse_lazy('home')


class TwoFactorAuthenticate(FormView):
    template_name = 'allauth_2fa/authenticate.html'
    form_class = TOTPAuthenticateForm
    success_url = SUCCESS_URL

    def dispatch(self, request, *args, **kwargs):
        # If the user is not about to enter their two-factor credentials,
        # redirect to the login page (they shouldn't be here!)
        if 'allauth_2fa_user_id' not in request.session:
            return redirect('account_login')
        return super(TwoFactorAuthenticate, self).dispatch(request, *args,
                                                           **kwargs)

    def get_form_kwargs(self):
        kwargs = super(TwoFactorAuthenticate, self).get_form_kwargs()
        user_id = self.request.session['allauth_2fa_user_id']
        kwargs['user'] = get_user_model().objects.get(id=user_id)
        return kwargs

    def form_valid(self, form):
        from django.contrib.auth import login
        if not hasattr(form.user, 'backend'):
            form.user.backend \
                = "allauth.account.auth_backends.AuthenticationBackend"
        login(self.request, form.user)
        return super(TwoFactorAuthenticate, self).form_valid(form)

two_factor_authenticate = TwoFactorAuthenticate.as_view()


class TwoFactorSetup(FormView):
    template_name = 'allauth_2fa/setup.html'
    form_class = TOTPDeviceForm
    success_url = reverse_lazy('two-factor-backup-tokens')

    def dispatch(self, request, *args, **kwargs):
        if request.user.totpdevice_set.filter(confirmed=True).exists():
            return HttpResponseRedirect(reverse_lazy('two-factor-backup-tokens'))

        request.user.totpdevice_set.filter(confirmed=False).delete()
        TOTPDevice(user=request.user, confirmed=False).save()

        return super(TwoFactorSetup, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, request):
        kwargs = super(TwoFactorSetup, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        return super(TwoFactorSetup, self).form_valid(form)

two_factor_setup = TwoFactorSetup.as_view()


class TwoFactorRemove(FormView):
    template_name = 'allauth_2fa/remove.html'
    form_class = TOTPDeviceRemoveForm
    success_url = reverse_lazy('two-factor-setup')

    def dispatch(self, request, *args, **kwargs):
        if request.user.totpdevice_set.exists():
            return super(TwoFactorRemove, self).dispatch(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(reverse_lazy('two-factor-setup'))

    def form_valid(self, form):
        form.save()
        return super(TwoFactorRemove, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TwoFactorRemove, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

two_factor_remove = TwoFactorRemove.as_view()


class TwoFactorBackupTokens(TemplateView):
    template_name = 'allauth_2fa/backup_tokens.html'

    def get_context_data(self, **kwargs):
        context = super(TwoFactorBackupTokens, self).get_context_data(*kwargs)
        static_device, _ = self.request.user.staticdevice_set.get_or_create(
            name='backup'
        )

        if static_device:
            context['backup_tokens'] = static_device.token_set.all()

        return context

    def post(self, request, *args, **kwargs):
        static_device, _ = request.user.staticdevice_set.get_or_create(
            name='backup'
        )
        static_device.token_set.all().delete()
        for _ in range(3):
            static_device.token_set.create(token=StaticToken.random_token())
        return self.get(request, *args, **kwargs)

two_factor_backup_tokens = TwoFactorBackupTokens.as_view()


class QRCodeGeneratorView(View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        content_type = 'image/svg+xml; charset=utf-8'

        name = request.GET.get('name', 'default')
        device = request.user.totpdevice_set\
            .filter(confirmed=False, name=name).first()

        if device is None or name == 'default':
            request.user.totpdevice_set.filter(confirmed=False).delete()
            device = TOTPDevice(user=request.user, name=name, confirmed=False)
            device.save()

        secret_key = b32encode(device.bin_key).decode('utf-8')
        issuer = 'getstream.io'

        otpauth_url = 'otpauth://totp/{label}?{query}'.format(
            label=quote('{issuer}: {username}'.format(
                issuer=issuer,
                username=request.user.username
            )),
            query=urlencode((
                ('secret', secret_key),
                ('digits', 6),
                ('issuer', issuer),
            ))
        )

        img = qrcode.make(otpauth_url, image_factory=SvgPathImage)
        response = HttpResponse(content_type=content_type)
        img.save(response)
        return response

two_factor_qr_code_generator = QRCodeGeneratorView.as_view()
