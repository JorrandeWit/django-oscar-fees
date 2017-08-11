from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _

from oscar.apps.checkout.signals import post_checkout

from .signals import update_order_with_fee


class FeesConfig(AppConfig):
    name = 'django_oscar_fees'
    label = 'django_oscar_fees'
    verbose_name = _('Fees')

    def ready(self):
        post_checkout.connect(update_order_with_fee)
