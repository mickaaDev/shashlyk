from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

class Shift(models.Model):
    cashier = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name=_("Кассир/Менеджер"))
    start_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Открытие смены"))
    end_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Закрытие смены"))
    
    start_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Наличные при открытии"))
    end_cash = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Наличные при закрытии (факт)"))
    
    is_active = models.BooleanField(default=True, verbose_name=_("Смена активна"))

    def __str__(self):
        status = "Активна" if self.is_active else "Закрыта"
        return f"Смена №{self.id} ({status}) — {self.cashier.username}"

    class Meta:
        verbose_name = _('Рабочая смена')
        verbose_name_plural = _('Рабочие смены')