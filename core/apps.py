from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class MenuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    # 🌟 This changes the text above Category/Product models:
    verbose_name = _('Управление Сменой')