from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # 🌟 Изменили 'get_station_display' на наш собственный метод 'display_station'
    list_display = ('name', 'display_station')
    list_filter = ('station',)
    search_fields = ('name',)

    # 🌟 Явно прописываем метод получения красивого имени цеха
    def display_station(self, obj):
        return obj.get_station_display()
    
    # Задаем красивое имя для шапки таблицы вместо "method" или "get_station_display"
    display_station.short_description = _("Куда отправлять чек (Цех)")
    display_station.admin_order_field = 'station'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'cost_price', 'display_margin', 'stock', 'is_active')
    
    # 🌟 Fixed: Changed from 'category__type' to 'category__station'
    list_filter = ('is_active', 'category__station', 'category')
    list_editable = ('price', 'cost_price', 'stock', 'is_active')
    search_fields = ('name',)

    def display_margin(self, obj):
        return f"{obj.margin} сом"
    
    display_margin.short_description = _("Прибыль (Маржа)")
    display_margin.admin_order_field = 'price'