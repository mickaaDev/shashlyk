from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone

# 🌟 Импортируем локальную модель из core и модель заказов из соседнего приложения orders
from .models import Shift
from orders.models import Order

@login_required
def shift_management(request):
    """Экран администратора. Если смена уже открыта — уходим на столы."""
    active_shift = Shift.objects.filter(is_active=True).first()
    
    # 🌟 ЕСЛИ СМЕНА УЖЕ ОТКРЫТА: не пускаем сюда, редиректим на столы
    if active_shift:
        return redirect('waiter_dashboard')
        
    # Если смена закрыта, показываем чистый экран открытия (без отчетов и таблиц)
    return render(request, 'core/shift_management.html', {
        'active_shift': active_shift,
    })


@login_required
def toggle_shift(request):
    """Обработчик открытия и закрытия смены."""
    if request.method == "POST":
        active_shift = Shift.objects.filter(is_active=True).first()
        
        if active_shift:
            # 🛑 ЗАКРЫТИЕ СМЕНЫ (этот блок сработает, только если мы вызовем его из другого места, например, кнопкой из панели)
            end_cash_fact = request.POST.get('end_cash', 0)
            active_shift.end_time = timezone.now()
            active_shift.end_cash = end_cash_fact
            active_shift.is_active = False
            active_shift.save()
            
            messages.success(request, "Смена успешно закрыта. Касса заблокирована.")
            return redirect('shift_management')
        else:
            # 🟢 ОТКРЫТИЕ СМЕНЫ
            start_cash = request.POST.get('start_cash', 0)
            new_shift = Shift.objects.create(
                cashier=request.user,
                start_cash=start_cash or 0,
                is_active=True
            )
            messages.success(request, f"Смена №{new_shift.id} успешно открыта! Приятной работы.")
            
            # 🌟 ПОСЛЕ ОТКРЫТИЯ: Сразу перенаправляем на главный экран столов ресторана
            return redirect('waiter_dashboard')
            
    return redirect('shift_management')