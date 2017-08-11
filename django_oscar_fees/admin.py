from django.contrib import admin

from .models import Condition, ConditionalFee, Fee, FeeLine, OrderFee


admin.site.register(Condition)
admin.site.register(ConditionalFee)
admin.site.register(Fee)
admin.site.register(FeeLine)
admin.site.register(OrderFee)
