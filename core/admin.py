from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.safestring import mark_safe
from django.db.models import Sum, F

from .models import Shift
from orders.models import OrderItem


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    # 1. Колонки в общем списке смен (объединили старые + общую выручку цехов)
    list_display = (
        'id', 
        'cashier', 
        'get_local_start_time', 
        'get_local_end_time', 
        'start_cash', 
        'end_cash', 
        'display_discrepancy',
        'total_shift_revenue',  # Добавили сумму в список смен
        'is_active'
    )
    
    # 2. Боковые фильтры для быстрой навигации
    list_filter = ('is_active', 'start_time', 'cashier')
    
    # 3. Глобальный поиск по ID смены или имени кассира
    search_fields = ('id', 'cashier__username', 'cashier__first_name', 'cashier__last_name')
    
    # 4. Возможность быстро закрыть смену прямо из списка
    list_editable = ('is_active',)

    # 5. Делаем временные метки и наш кастомный HTML-отчет доступными только для чтения
    readonly_fields = ('start_time', 'end_time', 'shift_departments_report')
    
    # 6. Красиво разбиваем страницу самой смены на блоки (Fieldsets)
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
        (_('Финансовая аналитика смены'), {
            'fields': ('shift_departments_report',),
            'description': _('Автоматический расчет выручки по цехам на основе закрытых чеков в рамках данной смены.')
        }),
    )

    # 🌟 Автоматический расчет расхождения в кассе
    def display_discrepancy(self, obj):
        if obj.is_active or obj.end_cash is None:
            return _("Смена открыта")
        
        diff = obj.end_cash - obj.start_cash
        if diff < 0:
            return f"{diff} сом (Недостача)"
        return f"+{diff} сом"
    
    display_discrepancy.short_description = _("Разница кассы")

    # 🌟 Локализованное время открытия
    def get_local_start_time(self, obj):
        if obj.start_time:
            local_time = timezone.localtime(obj.start_time)
            return date_format(local_time, format="d M Y (H:i)", use_l10n=True)
        return "-"
    get_local_start_time.short_description = _("Открыта в")
    get_local_start_time.admin_order_field = 'start_time'

    # 🌟 Локализованное время закрытия
    def get_local_end_time(self, obj):
        if obj.end_time:
            local_time = timezone.localtime(obj.end_time)
            return date_format(local_time, format="d M Y (H:i)", use_l10n=True)
        return _("В процессе")
    get_local_end_time.short_description = _("Закрыта в")
    get_local_end_time.admin_order_field = 'end_time'

    # 🌟 Общая выручка для колонки в списке всех смен
    def total_shift_revenue(self, obj):
        if not obj.start_time:
            return "0 сом"
            
        items_queryset = OrderItem.objects.filter(order__status='closed', order__closed_at__gte=obj.start_time)
        if obj.end_time:
            items_queryset = items_queryset.filter(order__closed_at__lte=obj.end_time)
        
        total = items_queryset.aggregate(total=Sum(F('quantity') * F('price_at_order')))['total'] or 0
        return f"{total:,} сом"
    
    total_shift_revenue.short_description = _("Выручка")

    # 🌟 Встроенная HTML-таблица с разбивкой по 3 цехам на странице смены
    def shift_departments_report(self, obj):
        if not obj.start_time:
            return _("Смена еще не начата")

        # Находим проданные позиции из закрытых заказов в интервале этой смены
        items_queryset = OrderItem.objects.filter(
            order__status='closed',
            order__closed_at__gte=obj.start_time
        )
        
        if obj.end_time:
            items_queryset = items_queryset.filter(order__closed_at__lte=obj.end_time)

        # Агрегация по трем цехам
        sales_by_dept = items_queryset.values('product__department').annotate(
            total_revenue=Sum(F('quantity') * F('price_at_order'))
        )

        # Формируем базовый словарь с нулями
        report_data = {'grill': 0, 'bar': 0, 'kitchen': 0}
        for entry in sales_by_dept:
            dept_code = entry['product__department']
            if dept_code in report_data:
                report_data[dept_code] = entry['total_revenue'] or 0

        # Рендерим чистую, адаптивную таблицу для стандартной темы админки Django
        html = f"""
        <table style="width: 100%; max-width: 600px; border-collapse: collapse; margin-top: 5px; border: 1px solid var(--border-color, #eee);">
            <thead>
                <tr style="background: var(--darkened-bg, #f8f8f8); border-bottom: 2px solid var(--border-color, #ccc); text-align: left;">
                    <th style="padding: 10px; font-weight: 600;">{_('Цех приготовления')}</th>
                    <th style="padding: 10px; text-align: right; font-weight: 600;">{_('Выручка за смену')}</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid var(--border-color, #eee);">
                    <td style="padding: 10px;">🔥 {_('Мангал / Гриль')}</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{report_data['grill']:,} сом</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-color, #eee);">
                    <td style="padding: 10px;">🍹 {_('Бар / Напитки')}</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{report_data['bar']:,} сом</td>
                </tr>
                <tr style="border-bottom: 2px solid var(--border-color, #ccc);">
                    <td style="padding: 10px;">🍳 {_('Горячий/Холодный цех')}</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{report_data['kitchen']:,} сом</td>
                </tr>
                <tr style="background: var(--selected-row, #f5f5f5); font-weight: bold; font-size: 1.1em;">
                    <td style="padding: 10px; color: var(--body-quiet-color, #666);">{_('Итого по цехам:')}</td>
                    <td style="padding: 10px; text-align: right; color: var(--link-color, #264b5d);">{sum(report_data.values()):,} сом</td>
                </tr>
            </tbody>
        </table>
        """
        return mark_safe(html)

    shift_departments_report.short_description = _("Распределение доходов")