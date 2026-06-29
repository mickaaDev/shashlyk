from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # 🌟 Fixed: Changed from 'get_type_display' to 'get_station_display'
    list_display = ('name', 'get_station_display')
    # 🌟 Fixed: Changed from 'type' to 'station'
    list_filter = ('station',)
    search_fields = ('name',)

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