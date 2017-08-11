from oscar.core.compat import MiddlewareMixin
from oscar.core.loading import get_model

from .applicator import Applicator
from .exceptions import InvalidMiddleware

Basket = get_model('basket', 'basket')


class BasketMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not hasattr(request, 'basket'):
            raise InvalidMiddleware('BasketMiddleware failed! '
                                    'You probably did not install Django Oscar'
                                    ' or have the MIDDLEWARE setting wrongly'
                                    ' ordered.')
        self.apply_fees_to_basket(request, request.basket)

    def apply_fees_to_basket(self, request, basket):
        if not basket.is_empty:
            Applicator().apply(basket, request.user, request)
