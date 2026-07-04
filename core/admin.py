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

        # 1. Выборка всех проданных позиций за период смены из закрытых чеков
        items_queryset = OrderItem.objects.filter(
            order__status='closed',
            order__closed_at__gte=obj.start_time
        )
        if obj.end_time:
            items_queryset = items_queryset.filter(order__closed_at__lte=obj.end_time)

        # Агрегируем выручку и себестоимость по цехам
        sales_by_dept = items_queryset.values('product__department').annotate(
            total_revenue=Sum(F('quantity') * F('price_at_order')),
            total_cost=Sum(F('quantity') * F('product__cost_price'))
        )

        report_data = {
            'grill': {'revenue': 0, 'cost': 0},
            'bar': {'revenue': 0, 'cost': 0},
            'kitchen': {'revenue': 0, 'cost': 0},
        }

        for entry in sales_by_dept:
            dept_code = entry['product__department']
            if dept_code in report_data:
                report_data[dept_code]['revenue'] = entry['total_revenue'] or 0
                report_data[dept_code]['cost'] = entry['total_cost'] or 0

        # Общие итоги по цехам
        total_revenue = sum(dept['revenue'] for dept in report_data.values())
        total_cost = sum(dept['cost'] for dept in report_data.values())
        total_margin = total_revenue - total_cost
        total_margin_percent = (total_margin / total_revenue * 100) if total_revenue > 0 else 0

        def get_row_metrics(revenue, cost):
            margin = revenue - cost
            margin_percent = (margin / revenue * 100) if revenue > 0 else 0
            return margin, margin_percent

        grill_margin, grill_pct = get_row_metrics(report_data['grill']['revenue'], report_data['grill']['cost'])
        bar_margin, bar_pct = get_row_metrics(report_data['bar']['revenue'], report_data['bar']['cost'])
        kitchen_margin, kitchen_pct = get_row_metrics(report_data['kitchen']['revenue'], report_data['kitchen']['cost'])

        # 2. ДОБАВЛЯЕМ: Сверка наличных (только если смена закрыта и заполнен факт)
        cash_reconciliation_html = ""
        if obj.end_time and obj.cash_at_close_fact is not None:
            # Предположим, что вся выручка пока идет как наличные. 
            # Если есть разделение, то вместо total_revenue здесь должна быть сумма чеков с payment_method='cash'
            cash_at_open = obj.cash_at_open or 0
            expected_cash = cash_at_open + total_revenue 
            discrepancy = obj.cash_at_close_fact - expected_cash
            
            if discrepancy == 0:
                disc_color, disc_text = "#27ae60", "Смена сведена идеально! (0 сом)"
            elif discrepancy > 0:
                disc_color, disc_text = "#2196F3", f"Излишек: +{discrepancy:,} сом"
            else:
                disc_color, disc_text = "#c0392b", f"Недостача: {discrepancy:,} сом"

            cash_reconciliation_html = f"""
            <h4 style="margin: 25px 0 10px 0; font-weight: 600; color: var(--body-quiet-color, #666);">📊 Сверка денежных средств в кассе:</h4>
            <table style="width: 100%; max-width: 850px; border-collapse: collapse; border: 1px solid var(--border-color, #eee); font-size: 0.95em;">
                <tr style="border-bottom: 1px solid var(--border-color, #eee);">
                    <td style="padding: 10px; width: 50%;">Ожидаемо в кассе (Начало + Выручка):</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{expected_cash:,} сом</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-color, #eee);">
                    <td style="padding: 10px;">Фактически сдано кассиром:</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{obj.cash_at_close_fact:,} сом</td>
                </tr>
                <tr style="background: var(--darkened-bg, #f8f8f8); font-weight: bold;">
                    <td style="padding: 10px;">Результат сверки:</td>
                    <td style="padding: 10px; text-align: right; color: {disc_color};">{disc_text}</td>
                </tr>
            </table>
            """

        # Собираем финальный интерфейс
        html = f"""
        <table style="width: 100%; max-width: 850px; border-collapse: collapse; margin-top: 5px; border: 1px solid var(--border-color, #eee); font-size: 0.95em;">
            <thead>
                <tr style="background: var(--darkened-bg, #f8f8f8); border-bottom: 2px solid var(--border-color, #ccc); text-align: left;">
                    <th style="padding: 12px 10px; font-weight: 600;">{_('Цех приготовления')}</th>
                    <th style="padding: 12px 10px; text-align: right; font-weight: 600;">{_('Выручка')}</th>
                    <th style="padding: 12px 10px; text-align: right; font-weight: 600;">{_('Себестоимость')}</th>
                    <th style="padding: 12px 10px; text-align: right; font-weight: 600;">{_('Чистая маржа')}</th>
                    <th style="padding: 12px 10px; text-align: right; font-weight: 600;">{_('Маржинальность')}</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid var(--border-color, #eee);">
                    <td style="padding: 10px;">🔥 {_('Мангал / Гриль')}</td>
                    <td style="padding: 10px; text-align: right;">{report_data['grill']['revenue']:,} сом</td>
                    <td style="padding: 10px; text-align: right; color: #c0392b;">{report_data['grill']['cost']:,} сом</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold; color: #27ae60;">{grill_margin:,} сом</td>
                    <td style="padding: 10px; text-align: right; color: var(--body-quiet-color, #666);">{grill_pct:.1f}%</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-color, #eee);">
                    <td style="padding: 10px;">🍹 {_('Бар / Напитки')}</td>
                    <td style="padding: 10px; text-align: right;">{report_data['bar']['revenue']:,} сом</td>
                    <td style="padding: 10px; text-align: right; color: #c0392b;">{report_data['bar']['cost']:,} сом</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold; color: #27ae60;">{bar_margin:,} сом</td>
                    <td style="padding: 10px; text-align: right; color: var(--body-quiet-color, #666);">{bar_pct:.1f}%</td>
                </tr>
                <tr style="border-bottom: 2px solid var(--border-color, #ccc);">
                    <td style="padding: 10px;">🍳 {_('Горячий/Холодный цех')}</td>
                    <td style="padding: 10px; text-align: right;">{report_data['kitchen']['revenue']:,} сом</td>
                    <td style="padding: 10px; text-align: right; color: #c0392b;">{report_data['kitchen']['cost']:,} сом</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold; color: #27ae60;">{kitchen_margin:,} сом</td>
                    <td style="padding: 10px; text-align: right; color: var(--body-quiet-color, #666);">{kitchen_pct:.1f}%</td>
                </tr>
                <tr style="background: var(--selected-row, #f5f5f5); font-weight: bold; font-size: 1.05em;">
                    <td style="padding: 12px 10px;">{_('Итого по заведению:')}</td>
                    <td style="padding: 12px 10px; text-align: right; color: var(--link-color, #264b5d);">{total_revenue:,} сом</td>
                    <td style="padding: 12px 10px; text-align: right; color: #c0392b;">{total_cost:,} сом</td>
                    <td style="padding: 12px 10px; text-align: right; color: #2196F3;">{total_margin:,} сом</td>
                    <td style="padding: 12px 10px; text-align: right; color: #2e7d32;">{total_margin_percent:.1f}%</td>
                </tr>
            </tbody>
        </table>
        {cash_reconciliation_html}
        """
        return mark_safe(html)