from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.



class Category(models.Model):
    # 🌟 These are your 3 fixed, unchangeable target printer/display lines
    STATION_CHOICES = (
        ('bar', 'Бар'),
        ('kitchen', 'Кухня'),
        ('grill', 'Мангал'),
    )
    
    # This allows unlimited menu sections (e.g., "Шашлыки", "Стейки", "Гарниры")
    name = models.CharField(max_length=50, unique=True, verbose_name=_("Название категории (напр. Салаты, Напитки)"))
    
    # This binds the entire category to one of your 3 fixed spots
    station = models.CharField(
        max_length=20, 
        choices=STATION_CHOICES, 
        default='kitchen',
        verbose_name=_("Куда отправлять чек (Цех)")
    )

    def __str__(self):
        return f"{self.name} -> [{self.get_station_display()}]"
    
    class Meta:
        verbose_name = _('Категория меню')
        verbose_name_plural = _('Категории меню')



class Product(models.Model):
    DEPARTMENT_CHOICES = [
        ('grill', '🔥 Мангал '),
        ('bar', '🍹 Бар / Напитки'),
        ('kitchen', '🍳 Горячий/Холодный цех'),
    ]
    department = models.CharField(
        max_length=20, 
        choices=DEPARTMENT_CHOICES, 
        default='kitchen', 
        verbose_name="Цех приготовления"
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT, 
        related_name='products', 
        verbose_name=_("Категория")
    )
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Название блюда/товара"))
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Цена продажи"))
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Цена закупа"))
    
    # Track inventory only for items that need it (e.g., bottled sodas, alcohol)
    # Kitchen and grill items can be left blank (Null) as they are cooked fresh
    stock = models.IntegerField(null=True, blank=True, verbose_name=_("Остаток на складе"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен (Показывать в меню)"))

    def __str__(self):
        return f"{self.name} — {self.price} сом"

    @property
    def margin(self):
        """Calculates net profit margin for a single unit."""
        return self.price - self.cost_price

    class Meta:
        verbose_name = _('Товар/Блюдо')
        verbose_name_plural = _('Товары и Блюда')
