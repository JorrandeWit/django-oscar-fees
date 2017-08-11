import operator
from decimal import Decimal as D
from decimal import ROUND_DOWN

from django.conf import settings
from django.core import exceptions
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import models
from django.template.defaultfilters import date as date_filter
from django.utils.timezone import get_current_timezone, now
from django.utils.translation import ugettext_lazy as _

from oscar.apps.offer import utils, abstract_models
from oscar.core.loading import get_model
from oscar.core.utils import get_default_currency
from oscar.models import fields
from oscar.templatetags.currency_filters import currency

from .managers import ActiveFeeManager
from .results import BasketFee, ZERO_FEE


class ConditionalFee(models.Model):
    """
    A conditional fee
    """
    name = models.CharField(
        _("Name"), max_length=128, unique=True,
        help_text=_("This is displayed within the customer's basket"))
    slug = fields.AutoSlugField(
        _("Slug"), max_length=128, unique=True, populate_from='name')
    description = models.TextField(_("Description"), blank=True,
                                   help_text=_("This is displayed on the fee"
                                               " browsing page"))

    SITE, USER, SESSION = ("Site", "User", "Session")
    TYPE_CHOICES = (
        (SITE, _("Site fee - available to all users")),
        (USER, _("User fee - available to certain types of user")),
        (SESSION, _("Session offer - temporary offer, available for "
                    "a user for the duration of their session")),
    )
    offer_type = models.CharField(
        _("Type"), choices=TYPE_CHOICES, default=SITE, max_length=128)

    # We track a status variable so it's easier to load offers that are
    # 'available' in some sense.
    OPEN, SUSPENDED, CONSUMED = "Open", "Suspended", "Consumed"
    STATUS_CHOICES = (
        (OPEN, OPEN),
        (SUSPENDED, SUSPENDED),
        (CONSUMED, CONSUMED),
    )
    status = models.CharField(_("Status"), max_length=64, choices=STATUS_CHOICES, default=OPEN)

    condition = models.ForeignKey(
        'django_oscar_fees.Condition',
        on_delete=models.CASCADE,
        verbose_name=_("Condition"))
    fee = models.ForeignKey(
        'django_oscar_fees.Fee',
        on_delete=models.CASCADE,
        verbose_name=_("Fee"))

    # AVAILABILITY

    # Range of availability.
    start_datetime = models.DateTimeField(
        _("Start date"), blank=True, null=True)
    end_datetime = models.DateTimeField(
        _("End date"), blank=True, null=True,
        help_text=_("Fees are active until the end of the 'end date'"))

    # Use this field to limit the number of times this fee can be applied in
    # total.  Note that a single order can apply an fee multiple times so
    # this is not necessarily the same as the number of orders that can use it.
    # Also see max_basket_applications.
    max_global_applications = models.PositiveIntegerField(
        _("Max global applications"),
        help_text=_("The number of times this fee can be used before it "
                    "is unavailable"), blank=True, null=True)

    # Use this field to limit the number of times this fee can be used by a
    # single user.  This only works for signed-in users - it doesn't really
    # make sense for sites that allow anonymous checkout.
    max_user_applications = models.PositiveIntegerField(
        _("Max user applications"),
        help_text=_("The number of times a single user may get this fee"),
        blank=True, null=True)

    # Use this field to limit the number of times this fee can be applied to
    # a basket (and hence a single order). Often, an fee should only be
    # usable once per basket/order, so this field will commonly be set to 1.
    max_basket_applications = models.PositiveIntegerField(
        _("Max basket applications"),
        blank=True, null=True,
        help_text=_("The number of times this fee can be applied to a "
                    "basket (and order)"))

    # Use this field to limit the amount of fee can lead to.
    # This can be helpful with budgeting.
    max_fee = models.DecimalField(
        _("Max fee"), decimal_places=2, max_digits=12, null=True,
        blank=True,
        help_text=_("When an fee has reached more to orders "
                    "than this threshold, then the fee becomes "
                    "unavailable"))

    # TRACKING
    # These fields are used to enforce the limits set by the
    # max_* fields above.

    total_fee = models.DecimalField(
        _("Total Fee"), decimal_places=2, max_digits=12,
        default=D('0.00'))
    num_applications = models.PositiveIntegerField(
        _("Number of applications"), default=0)
    num_orders = models.PositiveIntegerField(
        _("Number of Orders"), default=0)

    redirect_url = fields.ExtendedURLField(
        _("URL redirect (optional)"), blank=True)
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    objects = models.Manager()
    active = ActiveFeeManager()

    class Meta:
        app_label = 'django_oscar_fees'
        ordering = ['-date_created']
        verbose_name = _("Conditional fee")
        verbose_name_plural = _("Conditional fees")

    def save(self, *args, **kwargs):
        # Check to see if consumption thresholds have been broken
        if not self.is_suspended:
            if self.get_max_applications() == 0:
                self.status = self.CONSUMED
            else:
                self.status = self.OPEN

        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('offer:detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.name

    def clean(self):
        if (self.start_datetime and self.end_datetime and
                self.start_datetime > self.end_datetime):
            raise exceptions.ValidationError(
                _('End date should be later than start date'))

    @property
    def is_open(self):
        return self.status == self.OPEN

    @property
    def is_suspended(self):
        return self.status == self.SUSPENDED

    def suspend(self):
        self.status = self.SUSPENDED
        self.save()
    suspend.alters_data = True

    def unsuspend(self):
        self.status = self.OPEN
        self.save()
    unsuspend.alters_data = True

    def is_available(self, user=None, test_date=None):
        """
        Test whether this offer is available to be used
        """
        if self.is_suspended:
            return False
        if test_date is None:
            test_date = now()
        predicates = []
        if self.start_datetime:
            predicates.append(self.start_datetime > test_date)
        if self.end_datetime:
            predicates.append(test_date > self.end_datetime)
        if any(predicates):
            return False
        return self.get_max_applications(user) > 0

    def is_condition_satisfied(self, basket):
        return self.condition.proxy().is_satisfied(self, basket)

    def is_condition_partially_satisfied(self, basket):
        return self.condition.proxy().is_partially_satisfied(self, basket)

    def get_upsell_message(self, basket):
        return self.condition.proxy().get_upsell_message(self, basket)

    def apply_fee(self, basket):
        """
        Applies the benefit to the given basket and returns the discount.
        """
        if not self.is_condition_satisfied(basket):
            return ZERO_FEE
        return self.fee.proxy().apply(basket, self.condition.proxy(), self)

    def get_max_applications(self, user=None):
        """
        Return the number of times this fee can be applied to a basket for a
        given user.
        """
        if self.max_fee and self.total_fee >= self.max_fee:
            return 0

        # Hard-code a maximum value as we need some sensible upper limit for
        # when there are not other caps.
        limits = [10000]
        if self.max_user_applications and user:
            limits.append(max(0, self.max_user_applications -
                          self.get_num_user_applications(user)))
        if self.max_basket_applications:
            limits.append(self.max_basket_applications)
        if self.max_global_applications:
            limits.append(
                max(0, self.max_global_applications - self.num_applications))
        return min(limits)

    def get_num_user_applications(self, user):
        raise NotImplementedError('ConditionalFee.get_num_user_applications')
        OrderDiscount = get_model('order', 'OrderDiscount')
        aggregates = OrderDiscount.objects.filter(offer_id=self.id,
                                                  order__user=user)\
            .aggregate(total=models.Sum('frequency'))
        return aggregates['total'] if aggregates['total'] is not None else 0

    def shipping_discount(self, charge):
        return self.benefit.proxy().shipping_discount(charge)

    def record_usage(self, fee):
        self.num_applications += fee['freq']
        self.total_fee += fee['fee']
        self.num_orders += 1
        self.save()
    record_usage.alters_data = True

    def availability_description(self):
        """
        Return a description of when this offer is available
        """
        restrictions = self.availability_restrictions()
        descriptions = [r['description'] for r in restrictions]
        return "<br/>".join(descriptions)

    def availability_restrictions(self):  # noqa (too complex (15))
        restrictions = []
        if self.is_suspended:
            restrictions.append({
                'description': _("Offer is suspended"),
                'is_satisfied': False})

        if self.max_global_applications:
            remaining = self.max_global_applications - self.num_applications
            desc = _("Limited to %(total)d uses (%(remainder)d remaining)") \
                % {'total': self.max_global_applications,
                   'remainder': remaining}
            restrictions.append({'description': desc,
                                 'is_satisfied': remaining > 0})

        if self.max_user_applications:
            if self.max_user_applications == 1:
                desc = _("Limited to 1 use per user")
            else:
                desc = _("Limited to %(total)d uses per user") \
                    % {'total': self.max_user_applications}
            restrictions.append({'description': desc,
                                 'is_satisfied': True})

        if self.max_basket_applications:
            if self.max_user_applications == 1:
                desc = _("Limited to 1 use per basket")
            else:
                desc = _("Limited to %(total)d uses per basket") \
                    % {'total': self.max_basket_applications}
            restrictions.append({
                'description': desc,
                'is_satisfied': True})

        def hide_time_if_zero(dt):
            # Only show hours/minutes if they have been specified
            if dt.tzinfo:
                localtime = dt.astimezone(get_current_timezone())
            else:
                localtime = dt
            if localtime.hour == 0 and localtime.minute == 0:
                return date_filter(localtime, settings.DATE_FORMAT)
            return date_filter(localtime, settings.DATETIME_FORMAT)

        if self.start_datetime or self.end_datetime:
            today = now()
            if self.start_datetime and self.end_datetime:
                desc = _("Available between %(start)s and %(end)s") \
                    % {'start': hide_time_if_zero(self.start_datetime),
                       'end': hide_time_if_zero(self.end_datetime)}
                is_satisfied \
                    = self.start_datetime <= today <= self.end_datetime
            elif self.start_datetime:
                desc = _("Available from %(start)s") % {
                    'start': hide_time_if_zero(self.start_datetime)}
                is_satisfied = today >= self.start_datetime
            elif self.end_datetime:
                desc = _("Available until %(end)s") % {
                    'end': hide_time_if_zero(self.end_datetime)}
                is_satisfied = today <= self.end_datetime
            restrictions.append({
                'description': desc,
                'is_satisfied': is_satisfied})

        if self.max_fee:
            desc = _("Limited to a cost of %(max)s") % {
                'max': currency(self.max_fee)}
            restrictions.append({
                'description': desc,
                'is_satisfied': self.total_fee < self.max_fee})

        return restrictions

    @property
    def has_products(self):
        return self.condition.range is not None

    def products(self):
        """
        Return a queryset of products in this offer
        """
        Product = get_model('catalogue', 'Product')
        if not self.has_products:
            return Product.objects.none()

        cond_range = self.condition.range
        if cond_range.includes_all_products:
            # Return ALL the products
            queryset = Product.browsable
        else:
            queryset = cond_range.all_products()
        return queryset.filter(is_discountable=True).exclude(
            structure=Product.CHILD)


class Condition(abstract_models.AbstractCondition):
    class Meta:
        app_label = 'django_oscar_fees'
        verbose_name = _("Condition")
        verbose_name_plural = _("Conditions")
        default_related_name = 'fee_conditions'

    def proxy(self):
        """
        Return the proxy model
        """
        from . import conditions

        klassmap = {
            self.COUNT: conditions.CountCondition,
            self.VALUE: conditions.ValueCondition,
            self.COVERAGE: conditions.CoverageCondition
        }
        # Short-circuit logic if current class is already a proxy class.
        if self.__class__ in klassmap.values():
            return self

        field_dict = dict(self.__dict__)
        for field in list(field_dict.keys()):
            if field.startswith('_'):
                del field_dict[field]

        if self.proxy_class:
            klass = utils.load_proxy(self.proxy_class)
            # Short-circuit again.
            if self.__class__ == klass:
                return self
            return klass(**field_dict)
        if self.type in klassmap:
            return klassmap[self.type](**field_dict)
        raise RuntimeError("Unrecognised condition type (%s)" % self.type)

    def __str__(self):
        return self.name

    def can_apply_condition(self, line):
        """
        Determines whether the condition can be applied to a given basket line
        """
        if not line.stockrecord_id:
            return False
        return self.range.contains_product(line.product)


class Fee(models.Model):
    range = models.ForeignKey(
        'offer.Range',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        verbose_name=_("Range"))

    # Benefit types
    PERCENTAGE, FIXED = ("Percentage", "Absolute")
    TYPE_CHOICES = (
        (PERCENTAGE, _("Fee is a percentage of the basket's value")),
        (FIXED, _("Fee is a fixed amount")),
    )
    type = models.CharField(
        _("Type"), max_length=128, choices=TYPE_CHOICES, blank=True)

    # The value to use with the designated type.  This can be either an integer
    # (eg for multibuy) or a decimal (eg an amount) which is slightly
    # confusing.
    value = fields.PositiveDecimalField(
        _("Value"), decimal_places=2, max_digits=12, null=True, blank=True)

    # A custom benefit class can be used instead.  This means the
    # type/value/max_affected_items fields should all be None.
    proxy_class = fields.NullCharField(
        _("Custom class"), max_length=255, default=None)

    class Meta:
        # abstract = True
        app_label = 'django_oscar_fees'
        verbose_name = _("Fee")
        verbose_name_plural = _("Fees")

    def proxy(self):
        from . import fees

        klassmap = {
            self.PERCENTAGE: fees.PercentageFee,
            self.FIXED: fees.AbsoluteFee,
        }
        # Short-circuit logic if current class is already a proxy class.
        if self.__class__ in klassmap.values():
            return self

        field_dict = dict(self.__dict__)
        for field in list(field_dict.keys()):
            if field.startswith('_'):
                del field_dict[field]

        if self.proxy_class:
            klass = utils.load_proxy(self.proxy_class)
            # Short-circuit again.
            if self.__class__ == klass:
                return self
            return klass(**field_dict)

        if self.type in klassmap:
            return klassmap[self.type](**field_dict)
        raise RuntimeError("Unrecognised benefit type (%s)" % self.type)

    def __str__(self):
        return self.name

    @property
    def name(self):
        """
        A plaintext description of the benefit. Every proxy class has to
        implement it.

        This is used in the dropdowns within the offer dashboard.
        """
        return self.proxy().name

    @property
    def description(self):
        """
        A description of the benefit.
        Defaults to the name. May contain HTML.
        """
        return self.name

    def apply(self, basket, condition, offer):
        from . import conditions

        if isinstance(condition, conditions.ValueCondition):
            return ZERO_FEE

        discount = max(self.value, D('0.00'))
        return BasketFee(discount)

    def clean(self):
        if not self.type:
            return
        method_name = 'clean_%s' % self.type.lower().replace(' ', '_')
        if hasattr(self, method_name):
            getattr(self, method_name)()

    def get_applicable_lines(self, fee, basket, range=None):
        """
        Return the basket lines that are available for fee

        :basket: The basket
        :range: The range of products to use for filtering.  The fixed-price
                benefit ignores its range and uses the condition range
        """
        if range is None:
            range = self.range
        line_tuples = []
        for line in basket.all_lines():
            product = line.product

            if not range.contains(product):
                continue

            price = line.unit_effective_price
            if not price:
                # Avoid zero price products
                continue
            if line.quantity_without_discount == 0:
                continue
            line_tuples.append((price, line))

        # We sort lines to be cheapest first to ensure consistent applications
        return sorted(line_tuples, key=operator.itemgetter(0))

    def round(self, amount):
        """
        Apply rounding to discount amount
        """
        if hasattr(settings, 'OSCAR_OFFER_ROUNDING_FUNCTION'):
            return settings.OSCAR_OFFER_ROUNDING_FUNCTION(amount)
        return amount.quantize(D('.01'), ROUND_DOWN)


class FeeLine(models.Model):
    basket = models.ForeignKey('basket.Basket', on_delete=models.CASCADE,
                               related_name='fee_lines', verbose_name=_('Basket'))

    price_currency = models.CharField(_("Currency"), max_length=12, default=get_default_currency)
    price_excl_tax = models.DecimalField(_('Price excl. Tax'), decimal_places=2,
                                         max_digits=12, null=True)
    price_incl_tax = models.DecimalField(_('Price incl. Tax'), decimal_places=2,
                                         max_digits=12, null=True)

    fee = models.ForeignKey('django_oscar_fees.Fee', on_delete=models.CASCADE,
                            related_name='basket_lines', verbose_name=_("Fee"))

    quantity = models.PositiveIntegerField(_('Quantity'), default=1)

    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    class Meta:
        ordering = ['date_created', 'pk']
        verbose_name = _('Basket fee')
        verbose_name_plural = _('Basket fees')

    def __str__(self):
        return _(
            u"Basket #%(basket_id)d, Product #%(product_id)d, quantity"
            u" %(quantity)d") % {'basket_id': self.basket.pk,
                                 'product_id': self.product.pk,
                                 'quantity': self.quantity}

    def save(self, *args, **kwargs):
        if not self.basket.can_be_edited:
            raise PermissionDenied(
                _("You cannot modify a %s basket") % (
                    self.basket.status.lower(),))
        return super().save(*args, **kwargs)


# ORDER FEES

class OrderFee(models.Model):
    """
    A fee against an order.

    Normally only used for display purposes so an order can be listed with
    fees displayed separately even though in reality, the fees are
    applied at the basket total level.
    """
    order = models.ForeignKey(
        'order.Order',
        on_delete=models.CASCADE,
        related_name="fees",
        verbose_name=_("Order"))

    fee_id = models.PositiveIntegerField(
        _("Fee ID"), blank=True, null=True)
    fee_name = models.CharField(
        _("Fee name"), max_length=128, db_index=True, blank=True)
    amount = models.DecimalField(
        _("Amount"), decimal_places=2, max_digits=12, default=0)

    # Post-order offer applications can return a message to indicate what
    # action was taken after the order was placed.
    message = models.TextField(blank=True)

    class Meta:
        app_label = 'django_oscar_fees'
        verbose_name = _("Order Fee")
        verbose_name_plural = _("Order Fees")

    def save(self, **kwargs):
        if self.fee_id or not self.fee_name:
            fee = self.fee
            if fee:
                self.fee_name = fee.name

        super().save(**kwargs)

    def __str__(self):
        return _("Fee of %(amount)d from order %(order)s") % {
            'amount': self.amount, 'order': self.order}

    @property
    def fee(self):
        try:
            return Fee.objects.get(id=self.fee_id)
        except Fee.DoesNotExist:
            return None

    def description(self):
        return self.fee_name or u""
