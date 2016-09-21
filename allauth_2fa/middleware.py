from django.core.urlresolvers import resolve


class AllauthTwoFactorMiddleware(object):
    """Resets the login flow when another page is loaded halfway through."""

    def process_request(self, request):
        if not resolve(request.path).url_name.startswith(
                'two-factor-authenticate'):
            try:
                del request.session['allauth_2fa_user_id']
            except KeyError:
                pass
