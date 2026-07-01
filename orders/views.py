from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Table, Order, OrderItem
from menu.models import Category, Product
from core.models import Shift
from django.shortcuts import redirect
from django.db.models import Prefetch  
from django.urls import NoReverseMatch
from .utils import send_to_bar_printer, send_to_grill_printer, send_to_kitchen_printer



# @login_required
def waiter_dashboard(request):
    active_shift = Shift.objects.filter(is_active=True).first()

    if not active_shift:
        try:
            return redirect('core:shift_management')
        except NoReverseMatch:
            try:
                return redirect('shift_management')
            except NoReverseMatch:
                # Жесткий запасной вариант, если имена маршрутов вообще не резолвятся
                return redirect('/management/shift/')
    tables = Table.objects.filter(is_active=True).order_by('number')

    active_orders = Order.objects.filter(status='active').select_related('table', 'waiter')
    
    table_orders = {order.table_id: order for order in active_orders if order.table_id}
    context = {
        'tables': tables,
        'table_orders': table_orders,
        'active_shift': active_shift,
    }
    return render(request, 'orders/dashboard.html', context)


# @login_required
def order_detail(request, table_id):
    """Displays items inside an active order and shows the menu grid to add more items."""
    table = get_object_or_404(Table, id=table_id, is_active=True)
    
    # Find or automatically create an active order for this table
    order, created = Order.objects.get_or_create(
        table=table,
        status='active',
        defaults={'waiter': request.user}
    )
    
    # If the table was free, mark it as occupied
    if created and table.is_available:
        table.is_available = False
        table.save()

    # Optimization: Prefetch categories and their active products for the sidebar/grid
    menu_categories = Category.objects.prefetch_related(
        Prefetch('products', queryset=Product.objects.filter(is_active=True))
    )

    context = {
        'table': table,
        'order': order,
        'order_items': order.items.all().select_related('product'),
        'menu_categories': menu_categories,
    }
    return render(request, 'orders/order_detail.html', context)

@login_required
def add_item_to_order(request, order_id, product_id):
    """Increments or adds a product to an ongoing table check."""
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id, status='active')
        product = get_object_or_404(Product, id=product_id, is_active=True)
        
        # Check if item is already on the check
        order_item, item_created = OrderItem.objects.get_or_create(
            order=order,
            product=product,
            defaults={'price_at_order': product.price, 'quantity': 1}
        )
        
        if not item_created:
            order_item.quantity += 1
            order_item.save()
            
        # Re-trigger total computation hook inside the model
        order.update_total()
        
    return redirect('order_detail', table_id=order.table.id)


# @login_required
def increase_item(request, item_id):
    """Increments item quantity from the bill sidebar."""
    if request.method == "POST":
        item = get_object_or_404(OrderItem, id=item_id, order__status='active')
        item.quantity += 1
        item.save()
        item.order.update_total()
    return redirect('order_detail', table_id=item.order.table.id)

# @login_required
def decrease_item(request, item_id):
    """Decrements item quantity or deletes it if quantity drops to 0."""
    if request.method == "POST":
        item = get_object_or_404(OrderItem, id=item_id, order__status='active')
        order = item.order
        
        if item.quantity > 1:
            item.quantity -= 1
            item.save()
        else:
            item.delete()  # Remove completely if dropping below 1
            
        order.update_total()
    return redirect('order_detail', table_id=order.table.id)


@login_required
def send_order_to_kitchen(request, order_id):
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id, status='active')
        pending_items = order.items.filter(status='pending')
        
        if not pending_items.exists():
            messages.warning(request, "Нет новых блюд для отправки!")
            return redirect('order_detail', table_id=order.table.id)
        
        grill_items = pending_items.filter(product__department='grill')
        bar_items = pending_items.filter(product__department='bar')
        kitchen_items = pending_items.filter(product__department='kitchen')
        
        # --- МЕСТО ДЛЯ ПЕЧАТИ ВСТРЕЧЕК ---
        # Здесь вы сможете вызвать функции печати для каждого цеха отдельно, например:
        if grill_items.exists(): send_to_grill_printer(order, grill_items) 
        if bar_items.exists(): send_to_bar_printer(order, bar_items)
        if kitchen_items.exists(): send_to_kitchen_printer(order, kitchen_items)
        pending_items.update(status='sent')
        
        # 2. MERGE DUPLICATES: Объединяем одинаковые блюда, чтобы не плодить строки в чеке
        products_in_order = order.items.values_list('product_id', flat=True).distinct()
        
        for prod_id in products_in_order:
            sent_items = order.items.filter(product_id=prod_id, status='sent')
            if sent_items.count() > 1:
                primary_item = sent_items.first()
                total_qty = sum(item.quantity for item in sent_items)
                
                primary_item.quantity = total_qty
                primary_item.save()
                
                # Удаляем дубликаты строк
                sent_items.exclude(id=primary_item.id).delete()

        messages.success(request, "Новые дозаказы отправлены по цехам!")
        return redirect('order_detail', table_id=order.table.id)
        
    # На случай, если кто-то постучится GET запросом
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
def add_item_to_order(request, order_id, product_id):
    order = get_object_or_404(Order, id=order_id, status='active')
    product = get_object_or_404(Product, id=product_id)
    
    # 🌟 LOOK ONLY FOR AN UNSENT (PENDING) DRAFT OF THIS PRODUCT
    item, created = OrderItem.objects.get_or_create(
        order=order,
        product=product,
        status='pending',
        defaults={'price_at_order': product.price, 'quantity': 0}
    )
    
    item.quantity += 1
    item.save()
    order.update_total()
    return redirect('order_detail', table_id=order.table.id)



# @login_required
def close_order(request, order_id):
    """Closes out the order check and releases the billiard table."""
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id, status='active')
        
        # Guard rail: Block closure if unprinted drafts exist
        if order.items.filter(status='pending').exists():
            messages.error(request, "Нельзя закрыть счет! Сначала отправьте или удалите черновики.")
            return redirect('order_detail', table_id=order.table.id)
            
        # 1. Finalize and lock the bill details based on your model schema
        order.status = 'closed'
        order.closed_at = timezone.now()
        order.save()
        
        # 2. Release table ownership state back to green/available
        if order.table:
            table = order.table
            table.is_available = True
            table.save()
            messages.success(request, f"Стол №{table.number} успешно закрыт и рассчитан!")
        else:
            messages.success(request, f"Заказ №{order.id} успешно закрыт!")
            
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