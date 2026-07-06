from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Table, Order, OrderItem, Waiter
from menu.models import Category, Product
from core.models import Shift
from django.db.models import Prefetch  
from django.urls import NoReverseMatch
from django.db import transaction
from .utils import send_to_bar_printer, send_to_grill_printer, send_to_kitchen_printer, send_to_bill_printer



@login_required
def waiter_dashboard(request):
    # 🌟 АВТООЧИСТКА: Удаляем пустые черновики, если официант зашел в стол и ничего не заказал
    Order.objects.filter(status='draft', items__isnull=True).delete()

    active_shift = Shift.objects.filter(is_active=True).first()

    if not active_shift:
        try:
            return redirect('core:shift_management')
        except NoReverseMatch:
            try:
                return redirect('shift_management')
            except NoReverseMatch:
                return redirect('/management/shift/')
                
    tables = Table.objects.filter(is_active=True).order_by('number')

    # 🌟 ИСПРАВЛЕНИЕ ТУТ: select_related('waiter') подтягивает данные из нашей новой легкой таблицы Waiter
    active_orders = Order.objects.filter(status='active').select_related('table', 'waiter')
    
    table_orders = {order.table_id: order for order in active_orders if order.table_id}
    context = {
        'tables': tables,
        'table_orders': table_orders,
        'active_shift': active_shift,
    }
    return render(request, 'orders/dashboard.html', context)


@login_required
def print_prebill(request, order_id):
    """Печатает предчек без закрытия стола, если блюда были отправлены в работу."""
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id, status__in=['draft', 'active'])
        
        # 🌟 БАРЬЕР БЕЗОПАСНОСТИ: Проверяем, есть ли хоть одно отправленное блюдо
        # Если отправленных ('sent') позиций нет вообще, запрещаем печать
        if not order.items.filter(status='sent').exists():
            messages.error(
                request, 
                "Невозможно распечатать предчек! Сначала отправьте блюда на кухню/бар."
            )
            return redirect('order_detail', table_id=order.table.id)
        
        # Вызываем функцию печати из utils.py
        send_to_bill_printer(order, is_final=False)
        
        messages.success(request, f"Предчек для стола №{order.table.number} отправлен на печать!")
        
    return redirect('order_detail', table_id=order.table.id)

@login_required
def order_detail(request, table_id):
    table = get_object_or_404(Table, id=table_id)
    
    # 1. Проверяем, есть ли уже у стола открытый заказ
    order = Order.objects.filter(
        table=table, 
        status__in=['draft', 'active']
    ).first()
    
    # 2. Если заказа вообще нет, создаем его как DRAFT
    if not order:
        order = Order.objects.create(
            table=table,
            waiter=None,    # 🌟 ВАЖНО: Оставляем пустой ссылку на официанта, пока это черновик
            status='draft'  
        )
    
    order_items = order.items.all()
    
    # 3. Достаем список всех работающих сегодня официантов для формы выбора
    active_waiters = Waiter.objects.filter(is_active=True).order_by('name')
    
    # 4. Предварительно загружаем ТОЛЬКО активные продукты по категориям
    menu_categories = Category.objects.all().prefetch_related(
        Prefetch(
            'products', 
            queryset=Product.objects.filter(is_active=True).order_by('name')
        )
    )
    
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'table': table,
        'order_items': order_items,
        'menu_categories': menu_categories,
        'waiters': active_waiters,  # 🌟 Передаем список официантов в шаблон
    })

@login_required
def add_item_to_order(request, order_id, product_id):
    if request.method == 'POST':
        # Ищем заказ в статусе draft или active (чтобы пускало новые столы)
        order = get_object_or_404(Order, id=order_id, status__in=['draft', 'active'])
        product = get_object_or_404(Product, id=product_id)
        
        # Ищем именно черновик блюда (со статусом pending)
        item, created = OrderItem.objects.get_or_create(
            order=order,
            product=product,
            status='pending',
            defaults={'price_at_order': product.price, 'quantity': 0}
        )
        
        item.quantity += 1
        item.save()
        
        # Пересчитываем сумму
        order.update_total()  # Используем .update_total(), так как он у вас в остальных методах
        
        # Если это асинхронный запрос от нашего JS
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse("OK", status=200)
            
        # На случай обычного перехода по ссылке/форме
        return redirect('order_detail', table_id=order.table.id)
        
    raise Http404("Метод не поддерживается")


@login_required
def increase_item(request, item_id):
    """Увеличивает количество позиции в чеке (работает и для черновиков, и для активных)."""
    if request.method == "POST":
        # 🌟 Меняем order__status='active' на order__status__in=['draft', 'active']
        item = get_object_or_404(OrderItem, id=item_id, order__status__in=['draft', 'active'])
        item.quantity += 1
        item.save()
        
        # Используем метод, который есть у вашей модели (в коде выше были оба варианта, выберите рабочий)
        if hasattr(item.order, 'update_total'):
            item.order.update_total()
        else:
            item.order.update_total_amount()
            
    return redirect('order_detail', table_id=item.order.table.id)

@login_required
def decrease_item(request, item_id):
    """Уменьшает количество или удаляет позицию (работает и для черновиков, и для active)."""
    if request.method == "POST":
        # 🌟 Меняем order__status='active' на order__status__in=['draft', 'active']
        item = get_object_or_404(OrderItem, id=item_id, order__status__in=['draft', 'active'])
        order = item.order
        
        if item.quantity > 1:
            item.quantity -= 1
            item.save()
        else:
            item.delete()  # Удаляем совсем, если количество стало 0
            
        if hasattr(order, 'update_total'):
            order.update_total()
        else:
            order.update_total_amount()
            
    return redirect('order_detail', table_id=order.table.id)

@login_required
def send_order_to_kitchen(request, order_id):
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id, status__in=['draft', 'active'])
        pending_items = order.items.filter(status='pending')
        
        if not pending_items.exists():
            messages.warning(request, "Нет новых блюд для отправки!")
            return redirect('order_detail', table_id=order.table.id)
        
        grill_items = pending_items.filter(product__department='grill')
        bar_items = pending_items.filter(product__department='bar')
        kitchen_items = pending_items.filter(product__department='kitchen')
        
        # Включаем атомарную транзакцию
        with transaction.atomic():
            # 🌟 КЛЮЧЕВОЙ БЛОК: Считываем выбранного официанта при первой отправке заказа
            if order.status == 'draft':
                waiter_id = request.POST.get('waiter_id')
                if waiter_id:
                    order.waiter_id = waiter_id
                else:
                    messages.error(request, "Пожалуйста, выберите официанта перед отправкой заказа!")
                    return redirect('order_detail', table_id=order.table.id)
                
                order.status = 'active'
                order.save()

            # Списание остатков со склада ДО смены статуса на 'sent'
            for item in pending_items:
                product = item.product
                if hasattr(product, 'stock') and product.stock is not None:
                    product.stock -= item.quantity
                    product.save()

            # --- МЕСТО ДЛЯ ПЕЧАТИ ВСТРЕЧЕК ---
            if grill_items.exists(): send_to_grill_printer(order, grill_items) 
            if bar_items.exists(): send_to_bar_printer(order, bar_items)
            if kitchen_items.exists(): send_to_kitchen_printer(order, kitchen_items)
            
            # Переводим отправленные блюда в статус 'sent'
            pending_items.update(status='sent')
            
            # MERGE DUPLICATES: Объединяем одинаковые блюда в чеке
            products_in_order = order.items.values_list('product_id', flat=True).distinct()
            for prod_id in products_in_order:
                sent_items = order.items.filter(product_id=prod_id, status='sent')
                if sent_items.count() > 1:
                    primary_item = sent_items.first()
                    total_qty = sum(i.quantity for i in sent_items)
                    
                    primary_item.quantity = total_qty
                    primary_item.save()
                    
                    sent_items.exclude(id=primary_item.id).delete()

        messages.success(request, "Новые дозаказы отправлены по цехам! Остатки на складе обновлены.")
        return redirect('order_detail', table_id=order.table.id)
        
    order = get_object_or_404(Order, id=order_id)
    return redirect('order_detail', table_id=order.table.id)


@login_required
def resend_item_to_kitchen(request, item_id):
    """Allows a waiter to resend an individual item if a print/display fails."""
    if request.method == "POST":
        item = get_object_or_404(OrderItem, id=item_id, order__status='active')
        
        # Here you could hook up electronic thermal printing logs later.
        # For now, we simply alert the system it's re-sent.
        messages.info(request, f"Повторная отправка: {item.product.name}!")
        
    return redirect('order_detail', table_id=item.order.table.id)






@login_required
def close_order(request, order_id):
    """Closes out the order check, prints the final bill, and releases the table."""
    if request.method == "POST":
        # 🌟 БЕЗОПАСНЫЙ ПОИСК: Ищем просто по ID без паники и 404 вылетов
        order = Order.objects.filter(id=order_id).first()
        
        # Если такого ID вообще нет в базе данных
        if not order:
            print(f"⚠️ КРИТИЧЕСКАЯ ОШИБКА: Заказ с ID {order_id} не найден в базе!")
            messages.error(request, f"Ошибка: Чек №{order_id} не найден в системе.")
            return redirect('waiter_dashboard')
            
        # Если заказ нашли, но он уже закрыт/оплачен
        if order.status == 'closed':
            messages.warning(request, f"Чек №{order.id} уже был успешно закрыт ранее.")
            return redirect('waiter_dashboard')

        # Если в чеке только черновики и ничего не отправлено на кухню
        if not order.items.filter(status='sent').exists():
            messages.error(request, "Нельзя закрыть пустой счет! Сначала отправьте или удалите черновики.")
            return redirect('order_detail', table_id=order.table.id if order.table else 1)
            
        # Защитный барьер: проверяем оставшиеся черновики
        if order.items.filter(status='pending').exists():
            messages.error(request, "Нельзя закрыть счет! Сначала отправьте или удалите оставшиеся черновики.")
            return redirect('order_detail', table_id=order.table.id)
            
        # Перехватываем тип оплаты
        payment_method = request.POST.get('payment_method')
        if payment_method not in dict(Order.PAYMENT_METHODS):
            messages.error(request, "Пожалуйста, выберите корректный способ оплаты!")
            return redirect('order_detail', table_id=order.table.id)
            
        order.payment_method = payment_method
        
        # Автоматическая печать чека
        try:
            send_to_bill_printer(order, is_final=True)
        except Exception as e:
            messages.warning(request, f"Заказ закрыт, но возникла ошибка печати: {e}")

        # Фиксируем закрытие
        order.status = 'closed'
        order.closed_at = timezone.now()
        order.save()
        
        # Освобождаем стол
        if order.table:
            table = order.table
            table.is_available = True
            table.save()
            messages.success(request, f"Стол №{table.number} успешно рассчитан ({order.get_payment_method_display()})!")
            
        return redirect('waiter_dashboard')
        
    return redirect('waiter_dashboard')


@login_required
def view_bill(request, order_id):
    """Генерирует чистый гостевой чек для предпросмотра или печати."""
    order = get_object_or_404(Order, id=order_id)
    # Загружаем все позиции этого чека (и отправленные, и черновики)
    order_items = order.items.all()
    
    return render(request, 'orders/bill_detail.html', {
        'order': order,
        'order_items': order_items
    })