from .exceptions import FeesNotFound


def update_order_with_fee(sender, order, user, request, response, **kwargs):
    """
    This signal saves the OrderFee objects which is nothing else than
    just a registration of Fee use.
    """
    from .models import OrderFee

    try:
        for fee in sender._fees:
            order_fee = OrderFee(
                order=order,
                fee_id=fee.id,
                amount=fee.value
            )
            order_fee.save()
    except AttributeError:
        raise FeesNotFound("Please make sure you have placed the PaymentDetailsMixin"
                           " in Oscar's PaymentDetailsView.")
