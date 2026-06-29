from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.formats import date_format
from .models import Shift

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    # 1. Main table columns
    list_display = (
        'id', 
        'cashier', 
        'get_local_start_time', 
        'get_local_end_time', 
        'start_cash', 
        'end_cash', 
        'display_discrepancy', 
        'is_active'
    )
    
    # 2. Sidebar filters for quick navigation
    list_filter = ('is_active', 'start_time', 'cashier')
    
    # 3. Global search bar (lookup by cashier's name or shift number)
    search_fields = ('id', 'cashier__username', 'cashier__first_name', 'cashier__last_name')
    
    # 4. Prevent editing sensitive historical data directly from the list view
    # Only 'is_active' is left editable if a manager needs to force-close a shift
    list_editable = ('is_active',)

    # 5. Form field organization when clicking into a shift
    readonly_fields = ('start_time', 'end_time')
    fieldsets = (
        (_('Основная информация'), {
            'fields': ('cashier', 'is_active')
        }),
        (_('Временные метки'), {
            'fields': ('start_time', 'end_time')
        }),
        (_('Кассовый учёт (Сом)'), {
            'fields': ('start_cash', 'end_cash')
        }),
    )

    # 🌟 Calculate cash discrepancies automatically
    def display_discrepancy(self, obj):
        if obj.is_active or obj.end_cash is None:
            return _("Смена открыта")
        
        # Note: In a production system, you would calculate: (end_cash - start_cash - total_orders_revenue)
        # For now, this highlights the difference between starting and closing values
        diff = obj.end_cash - obj.start_cash
        if diff < 0:
            return f"{diff} сом (Недостача)"
        return f"+{diff} сом"
    
    display_discrepancy.short_description = _("Разница кассы")

    # 🌟 Localized time formatting for Start Time
    def get_local_start_time(self, obj):
        if obj.start_time:
            local_time = timezone.localtime(obj.start_time)
            return date_format(local_time, format="d M Y (H:i)", use_l10n=True)
        return "-"
    get_local_start_time.short_description = _("Открыта в")
    get_local_start_time.admin_order_field = 'start_time'

    # 🌟 Localized time formatting for End Time
    def get_local_end_time(self, obj):
        if obj.end_time:
            local_time = timezone.localtime(obj.end_time)
            return date_format(local_time, format="d M Y (H:i)", use_l10n=True)
        return _("В процессе")
    get_local_end_time.short_description = _("Закрыта в")
    get_local_end_time.admin_order_field = 'end_time'