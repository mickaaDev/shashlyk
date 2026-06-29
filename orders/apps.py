from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'
    # 🌟 This changes the text above Table/Order models:
    verbose_name = _('Работа с Заказами')