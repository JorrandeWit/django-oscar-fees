![Oscar](https://github.com/django-oscar/django-oscar/raw/master/docs/images/logos/oscar.png)

# Django Oscar Fees

This module will provide you the possibility to handle fees in [Django Oscar](https://github.com/django-oscar/django-oscar). You may apply absolute valued fees or relative valued fees (relative to the basket total). Conditions such as basket values may be applied. Most code is based on the Django Oscar Offer module.

#### Use case example: ####
- *Orders with a total less than €100 pay a €10 fee.*
- *Users pay a 10% fee on their first Order.*

## Installation ##

The easiest way to install is with [pip](https://pip.pypa.io).
```
$ pip install django-oscar-fees
```

## Getting Started ##

X steps are needed to get Django Oscar Fees rolling.

1. Append `django_oscar_fees` to your registered installed apps.
```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_oscar_fees',
```

2. Place the required `django_oscar_fees.middleware.BasketMiddleware` into your settings.
```python
# settings.py
MIDDLEWARE = [
    ...
    # It is important that the original Oscar BasketMiddleware is placed above the new Middleware!
    'oscar.apps.basket.middleware.BasketMiddleware',
    ...
    'django_oscar_fees.middleware.BasketMiddleware',
]
```

3. Place the `PaymentDetailsMixin` in your forked `checkout` app as shown.
If you have not yet forked the `checkout` app, [the docs will explain you how](http://django-oscar.readthedocs.io/en/latest/topics/customisation.html#fork-the-oscar-app).
```python
# checkout/views.py
from oscar.apps.checkout import views as oscar_views

from django_oscar_fees.mixins import PaymentDetailsMixin as FeeMixin

class PaymentDetailsView(FeeMixin, oscar_views.PaymentDetailsView):
    pass
```

## Under Construction ##
The module is under construction. Therefore, the relative fee's will raise an `NotImplementedError`.

## Support ##
The module is built for and tested on:
- Django 1.9, 1.10, 1.11;
- Python 3.x;

## License ##
[BSD (Berkeley Software Distribution) License](https://opensource.org/licenses/bsd-license.php).
Copyright (c) 2017, Jorran de Wit.
