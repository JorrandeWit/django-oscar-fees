import logging
from itertools import chain

from django.db.models import Q
from django.utils.timezone import now

from .models import ConditionalFee
from .results import FeeApplications

logger = logging.getLogger('oscar.offers')


class Applicator(object):

    def apply(self, basket, user=None, request=None):
        """
        Apply all relevant fees to the given basket.
        """
        fees = self.get_fees(basket, user, request)
        self.apply_fees(basket, fees)

    def apply_fees(self, basket, fees):
        applications = FeeApplications()
        for fee in fees:
            num_applications = 0
            # Keep applying the offer until either
            # (a) We reach the max number of applications for the offer.
            # (b) The benefit can't be applied successfully.
            while num_applications < fee.get_max_applications(basket.owner):
                result = fee.apply_fee(basket)
                num_applications += 1
                if not result.is_successful:
                    break

                applications.add(fee, result)
                basket.total_test += 1
                if result.is_final:
                    break

        # Store this list of fees with the basket so it can be
        # rendered in templates
        basket.fee_applications = applications

    def get_fees(self, basket, user=None, request=None):
        """
        Return all fees to apply to the basket.

        This method should be subclassed and extended to provide more
        sophisticated behaviour.  For instance, you could load extra offers
        based on the session or the user type.
        """
        site_fees = self.get_site_fees()
        user_fees = self.get_user_fees(user)
        session_fees = self.get_session_fees(request)

        return list(chain(session_fees, user_fees, site_fees))

    def get_site_fees(self):
        """
        Return site offers that are available to all users
        """
        cutoff = now()
        date_based = Q(
            Q(start_datetime__lte=cutoff),
            Q(end_datetime__gte=cutoff) | Q(end_datetime=None),
        )

        nondate_based = Q(start_datetime=None, end_datetime=None)

        qs = ConditionalFee.objects.filter(
            date_based | nondate_based,
            offer_type=ConditionalFee.SITE,
            status=ConditionalFee.OPEN)
        # Using select_related with the condition/benefit ranges doesn't seem
        # to work.  I think this is because both the related objects have the
        # FK to range with the same name.
        return qs.select_related('condition', 'fee')

    def get_user_fees(self, user):
        """
        Returns fees linked to this particular user.

        Eg: student users might pay 25% extra
        """
        return []

    def get_session_fees(self, request):
        """
        Returns temporary offers linked to the current session.

        Eg: visitors coming from an affiliate site pay a 10% fee
        """
        return []
