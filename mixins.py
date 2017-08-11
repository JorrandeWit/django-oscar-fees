
class PaymentDetailsMixin:
    def build_submission(self, **kwargs):
        """
        Here the Fees will be added to the PaymentDetailsView itself so we
        can later on append registrations to the Order placed.

        Also, here is where the Order totals are raised with the
        Fee totals!
        """
        submission = super().build_submission(**kwargs)
        self._fees = []
        if hasattr(self.request.basket, '_fees') and submission['order_total']:
            self._fees = self.request.basket._fees
            for fee in self._fees:
                submission['order_total'].excl_tax += fee.value
                submission['order_total'].incl_tax += fee.value
        return submission
