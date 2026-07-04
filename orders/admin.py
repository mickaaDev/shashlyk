from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Table, Order, OrderItem
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Sum, F


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('number', 'is_available', 'is_active')
    list_filter = ('is_available', 'is_active')
    list_editable = ('is_available', 'is_active')
    search_fields = ('number',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ('product', 'quantity', 'status', 'price_at_order')
    extra = 0
    raw_id_fields = ('product',)  # Speed boost if your menu grows large
    
    # 1. Completely remove the rightmost "Delete?" checkbox column
    can_delete = False

    # 2. Block deletes programmatically on server side
    def has_delete_permission(self, request, obj=None):
        return False

    # 3. Handle locked items within the receipt breakdown lines view
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == 'closed':
            return ('product', 'quantity', 'status', 'price_at_order')
        return ('price_at_order',)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status == 'closed':
            return False  # Ссылка "Добавить еще один..." исчезнет для закрытых чеков
        return True


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'table', 'waiter', 'status', 'created_at', 'closed_at', 
        'formatted_total_amount', 'get_total_cost', 'get_net_profit', 'view_bill_button'
    )
    list_filter = ('status', 'created_at', 'waiter', 'table')
    search_fields = ('id', 'waiter__username', 'table__number')
    
    inlines = [OrderItemInline]

    # Global safety rails: Fields that can never be modified manually
    # Added financial calculations to the baseline read-only array
    base_readonly = ['total_amount', 'get_total_cost', 'get_net_profit', 'created_at', 'closed_at']

    def get_readonly_fields(self, request, obj=None):
        # Always lock core financials, if closed, drop absolute flat-text lock across the header
        if obj and obj.status == 'closed':
            return self.base_readonly + ['table', 'waiter', 'status', 'payment_method']
        return self.base_readonly + ['table', 'waiter', 'status', 'payment_method']

    fieldsets = (
        (_('Основная информация'), {
            'fields': ('table', 'waiter', 'status', 'payment_method')
        }),
        (_('Временные метки и Финансы'), {
            'fields': ('total_amount', 'get_total_cost', 'get_net_profit', 'created_at', 'closed_at'),
        }),
    )

    def has_delete_permission(self, request, obj=None):
        # Strict protection: closed/archived final records cannot be deleted from db
        if obj and obj.status == 'closed':
            return False
        return True

    @admin.display(description=_("Итого к оплате"))
    def formatted_total_amount(self, obj):
        return f"{obj.total_amount or 0} сом"

    # 📈 Financial Calculator: Total Cost Price (Себестоимость)
    @admin.display(description=_("Себестоимость"))
    def get_total_cost(self, obj):
        # Calculates sum of (item.quantity * item.product.cost_price)
        result = obj.items.aggregate(
            total_cost=Sum(F('quantity') * F('product__cost_price'))
        )['total_cost']
        return f"{result:,.2f} сом" if result else "0.00 сом"

    # 📈 Financial Calculator: Net Profit (Чистая прибыль)
    @admin.display(description=_("Чистая прибыль"))
    def get_net_profit(self, obj):
        # Total selling price minus total purchase cost price
        total_sales = obj.total_amount or 0
        total_cost = obj.items.aggregate(
            total_cost=Sum(F('quantity') * F('product__cost_price'))
        )['total_cost'] or 0
        
        profit = total_sales - total_cost
        return f"{profit:,.2f} сом"

    @admin.display(description=_("Действие"))
    def view_bill_button(self, obj):
        from django.urls import reverse, NoReverseMatch
        
        try:
            # 1. Try checking using your application's namespace nickname prefix
            url = reverse('orders:view_bill', args=[obj.id])
        except NoReverseMatch:
            try:
                # 2. Fall back to standard global root if namespace configuration isn't active
                url = reverse('view_bill', args=[obj.id])
            except NoReverseMatch:
                # 3. Prevent admin page from throwing a 500 server crash if route misfires
                return mark_safe('<span class="text-muted">Route missing</span>')
                
        return mark_safe(f'<a class="button" href="{url}" target="_blank" style="background-color: #3498db; color: white; padding: 3px 10px; font-weight: bold; text-decoration: none; border-radius: 4px;">📄 Чек</a>')