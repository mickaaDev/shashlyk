from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from menu.models import Product

class Table(models.Model):
    number = models.CharField(max_length=10, unique=True, verbose_name=_("Номер стола"))
    is_available = models.BooleanField(default=True, verbose_name=_("Доступен/Свободен"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен (Существует в зале)"))
    def __str__(self):
        return f"Стол №{self.number}"

    class Meta:
        verbose_name = _('Стол')
        verbose_name_plural = _('Столы')



class Order(models.Model):
    STATUS_CHOICES = (
        ('active', _('Открыт (Обслуживание)')),
        ('closed', _('Оплачен (Закрыт)')),
        ('cancelled', _('Отменен')),
    )
    
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name=_("Стол"))
    waiter = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name=_("Официант"))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active', verbose_name=_("Статус"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Открыт в"))
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Закрыт в"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Итого к оплате"))

    def update_total(self):
        self.total_amount = sum(item.get_total_price() for item in self.items.all())
        self.save()

    def __str__(self):
        # Safely fall back if the table was removed or set to NULL
        table_num = self.table.number if self.table else _("Удален/Нет")
        return f"Счет №{self.id} ({table_num})"

    class Meta:
        verbose_name = _('Счет')
        verbose_name_plural = _('Счета (Чеки)')


class OrderItem(models.Model):
    PRINT_STATUS_CHOICES = (
        ('pending', _('Ждет отправки')),   # Waiter is still adding items on the screen
        ('sent', _('Отправлен на печать')), # Ticket was sent to Bar/Kitchen/Grill
        ('ready', _('Готово')),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name=_("Заказ"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name=_("Блюдо/Товар"))
    quantity = models.PositiveIntegerField(default=1, verbose_name=_("Кол-во"))
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Цена при заказе"))

    status = models.CharField(max_length=15, choices=PRINT_STATUS_CHOICES, default='pending', verbose_name=_("Статус печати"))
    comment = models.CharField(max_length=150, blank=True, null=True, verbose_name=_("Комментарий к блюду (напр. без лука)"))
    def get_total_price(self):
        return self.quantity * self.price_at_order
    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"
    def save(self, *args, **kwargs):
        if not self.pk and not self.price_at_order:
            self.price_at_order = self.product.price
        super().save(*args, **kwargs)
        self.order.update_total()

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.update_total()

    class Meta:
        verbose_name = _('Элемент заказа')
        verbose_name_plural = _('Элементы заказа')