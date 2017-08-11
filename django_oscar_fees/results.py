from decimal import Decimal as D


class FeeApplications(object):
    """
    A collection of fee applications.

    Each fee application is stored as a dict which has fields for:

    * The fee that led to the successful application
    * The result instance
    * The number of times the fee was successfully applied
    """
    def __init__(self):
        self.applications = {}

    def __iter__(self):
        return self.applications.values().__iter__()

    def __len__(self):
        return len(self.applications)

    def add(self, fee, result):
        if fee.id not in self.applications:
            self.applications[fee.id] = {
                'fee': fee,
                'result': result,
                'name': fee.name,
                'description': result.description,
                'freq': 0,
                'amount': D('0.00')}
        self.applications[fee.id]['amount'] += result.fee
        self.applications[fee.id]['freq'] += 1

    @property
    def fees(self):
        """
        Return fees
        """
        fees = []
        for application in self.applications.values():
            if application['amount'] > 0:
                fees.append(application)
        return fees

    @property
    def voucher_discounts(self):
        """
        Return basket discounts from vouchers.
        """
        discounts = []
        for application in self.applications.values():
            if application['voucher'] and application['discount'] > 0:
                discounts.append(application)
        return discounts

    @property
    def shipping_discounts(self):
        """
        Return shipping discounts
        """
        discounts = []
        for application in self.applications.values():
            if application['result'].affects_shipping:
                discounts.append(application)
        return discounts

    @property
    def grouped_voucher_discounts(self):
        """
        Return voucher discounts aggregated up to the voucher level.

        This is different to the voucher_discounts property as a voucher can
        have multiple offers associated with it.
        """
        voucher_discounts = {}
        for application in self.voucher_discounts:
            voucher = application['voucher']
            if voucher.code not in voucher_discounts:
                voucher_discounts[voucher.code] = {
                    'voucher': voucher,
                    'discount': application['discount'],
                }
            else:
                voucher_discounts[voucher.code] += application.discount
        return voucher_discounts.values()

    @property
    def post_order_actions(self):
        """
        Return successful offer applications which didn't lead to a discount
        """
        applications = []
        for application in self.applications.values():
            if application['result'].affects_post_order:
                applications.append(application)
        return applications

    @property
    def offers(self):
        """
        Return a dict of offers that were successfully applied
        """
        return dict([(a['offer'].id, a['offer']) for a in
                     self.applications.values()])


class ApplicationResult(object):
    is_final = is_successful = False
    fee = D('0.00')
    description = None


class BasketFee(ApplicationResult):
    """
    For when an offer application leads to a simple fee on the basket
    """
    is_final = True

    def __init__(self, amount):
        self.fee = amount

    @property
    def is_successful(self):
        return self.fee > 0

    def __str__(self):
        return '<Basket fee of %s>' % self.fee

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.fee)


# Helper global as returning zero fee is quite common
ZERO_FEE = BasketFee(D('0.00'))
