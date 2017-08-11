from decimal import Decimal as D

from django.utils.translation import ugettext_lazy as _

from oscar.apps.offer import conditions, utils
from oscar.templatetags.currency_filters import currency

from .models import Fee
from .results import BasketFee, ZERO_FEE

__all__ = [
    'PercentageFee', 'AbsoluteFee'
]


def apply_fee_to_line(line, line_fee, quantity):
    """
    Apply a given discount to the passed line
    """
    # Set if not already
    if not hasattr(line, '_fee_amount'):
        line._fee_amount = D('0.00')
    if not hasattr(line, '_fee_quantity'):
        line._fee_quantity = 0

    # Apply
    line._fee_amount += line_fee
    line._fee_quantity += int(quantity)


def apply_fee_to_basket(basket, fee, fees_amount, quantity):
    """
    Apply a given discount to the passed basket
    """
    # Set if not already
    if not hasattr(basket, '_total_fees_amount'):
        basket._total_fees_amount = D('0.00')
    if not hasattr(basket, '_fees'):
        basket._fees = []
    print('Add fee: €', fees_amount)

    # Apply
    basket._fees.append(fee)
    basket._total_fees_amount += fees_amount


class PercentageFee(Fee):
    """
    Give a percentage fee
    """
    _description = _("%(value)s%% fee on %(range)s")

    @property
    def name(self):
        return self._description % {
            'value': self.value,
            'range': self.range.name}

    @property
    def description(self):
        return self._description % {
            'value': self.value,
            'range': utils.range_anchor(self.range)}

    class Meta:
        app_label = 'django_oscar_fees'
        proxy = True
        verbose_name = _("Percentage fee")
        verbose_name_plural = _("Percentage fees")

    def apply(self, basket, condition, offer, discount_percent=None,
              max_total_fee=None):
        raise NotImplementedError


class AbsoluteFee(Fee):
    """
    A fee that applies with an fixed price to the basket
    """
    _description = _("%(value)s fee on %(range)s")

    @property
    def name(self):
        return self._description % {
            'value': currency(self.value),
            'range': self.range.name.lower()}

    @property
    def description(self):
        return self._description % {
            'value': currency(self.value),
            'range': utils.range_anchor(self.range)}

    class Meta:
        app_label = 'django_oscar_fees'
        proxy = True
        verbose_name = _("Absolute fee")
        verbose_name_plural = _("Absolute fees")

    def apply(self, basket, condition, offer, fee_amount=None,
              max_total_fee=None):
        if fee_amount is None:
            fee_amount = self.value

        if max_total_fee is not None:
            fee_amount = min(fee_amount, max_total_fee)

        if fee_amount == 0:
            return ZERO_FEE

        line_tuples = self.get_applicable_lines(offer, basket,
                                                range=condition.range)
        if not line_tuples:
            return ZERO_FEE

        #
        # # Determine the lines to consume
        num_permitted = int(condition.value)
        num_affected = 0
        # value_affected = D('0.00')
        covered_lines = []
        for price, line in line_tuples:
            if isinstance(condition, conditions.CoverageCondition):
                quantity_affected = 1
            else:
                quantity_affected = line.quantity
            num_affected += quantity_affected
            # value_affected += quantity_affected * price
            covered_lines.append((price, line, quantity_affected))
            if num_affected >= num_permitted:
                break

        # Apply discount to the affected lines
        # Apply discount to the affected lines
        fee_applied = D('0.00')
        last_line = covered_lines[-1][1]
        for price, line, quantity in covered_lines:
            if line == last_line:
                # If last line, we just take the difference to ensure that
                # rounding doesn't lead to an off-by-one error
                line_fee = fee_amount - fee_applied
            else:
                line_fee = self.round((fee_amount * quantity) / num_affected)
            apply_fee_to_line(line, line_fee, quantity)
            fee_applied += line_fee

        apply_fee_to_basket(basket, self, fee_amount, 1)
        return BasketFee(fee_amount)
