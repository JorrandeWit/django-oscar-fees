from django.db import models
from django.utils.timezone import now


class ActiveFeeManager(models.Manager):
    """
    For searching/creating fees within their date range
    """
    def get_queryset(self):
        cutoff = now()
        return super(ActiveFeeManager, self).get_queryset().filter(
            models.Q(end_datetime__gte=cutoff) | models.Q(end_datetime=None),
            start_datetime__lte=cutoff).filter(status=self.model.OPEN)
