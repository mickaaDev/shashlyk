from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.formats import date_format
from .models import Table, Order, OrderItem

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('number', 'is_available', 'is_active')
    list_filter = ('is_available', 'is_active')
    list_editable = ('is_available', 'is_active')
    search_fields = ('number',)


# This allows managing individual dishes inside the Order page directly
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ('product',)  # Speed boost if your menu grows large
    readonly_fields = ('price_at_order',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # 1. Main Table Display with Localized Time Conversions
    list_display = ('id', 'table', 'waiter', 'status', 'get_local_created_at', 'total_amount')
    list_filter = ('status', 'created_at', 'waiter')
    list_editable = ('status',)
    search_fields = ('id', 'table__number', 'waiter__username')
    
    # 2. Attach the inline item editor
    inlines = [OrderItemInline]

    # 3. Timezone Protection Rules for Admin Lists:
    def get_local_created_at(self, obj):
        if obj.created_at:
            # Explicitly force conversion to Asia/Bishkek time
            local_time = timezone.localtime(obj.created_at)
            return date_format(local_time, format="d M Y (H:i)", use_l10n=True)
        return "-"
    
    get_local_created_at.short_description = _("Открыт в")
    get_local_created_at.admin_order_field = 'created_at'  # Keeps column sortable