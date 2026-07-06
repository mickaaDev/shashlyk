from django.utils import timezone

def generate_ticket_text(order, items, department_name):
    """
    Базовый генератор текста встречки для поваров (только новые блюда цеха).
    """
    if not items.exists():
        return None

    lines = []
    lines.append("==================================")
    lines.append(f"   ВСТРЕЧКА: {department_name.upper()}")
    lines.append("==================================")
    lines.append(f"Чек: #{order.id}")
    lines.append(f"Стол: №{order.table.number if order.table else 'Без стола'}")
    # Change line 16 in /home/micka/Proejcts/shashlik/shashlyk/orders/utils.py to:
    lines.append(f"Официант: {order.waiter.name if order.waiter else 'Система'}")
    lines.append(f"Время: {timezone.now().strftime('%H:%M:%S')}")
    lines.append("----------------------------------")
    
    for item in items:
        lines.append(f"{item.product.name:<24} x {item.quantity}")
        # Проверяем наличие комментария (атрибут может называться comment)
        if hasattr(item, 'comment') and item.comment:
            lines.append(f"  * ПРИМЕЧАНИЕ: {item.comment}")
            
    lines.append("----------------------------------")
    lines.append("\n\n\n\n\n") 
    return "\n".join(lines)


def generate_bill_text(order, is_final=False):
    """
    Генератор текста для КЛИЕНТСКОГО ЧЕКА (Предчек или Финальный чек).
    Включает ВСЕ позиции заказа, цены, количество, итоговую сумму и тип оплаты.
    """
    lines = []
    lines.append("==================================")
    lines.append("          SHASHLYK POS            ")
    if is_final:
        lines.append("         ФИНАЛЬНЫЙ ЧЕК            ")
    else:
        lines.append("            ПРЕДЧЕК               ")
    lines.append("==================================")
    
    # Основная информация о заказе
    lines.append(f"Заказ:    #{order.id}")
    lines.append(f"Стол:     №{order.table.number if order.table else 'Без стола'}")
    lines.append(f"Официант: {order.waiter.name if order.waiter else 'Система'}")
    lines.append(f"Дата:     {timezone.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append("----------------------------------")
    
    # Шапка таблицы (Ширина стандартной ленты 58мм ~ 32-34 символа)
    # Распределяем: Название(14) Кол(4) Цена(6) Сумма(7) -> Итого 31 символ + пробелы
    lines.append(f"{'Наименование':<14} {'Кол':<4} {'Цена':<6} {'Сумма'}")
    lines.append("----------------------------------")
    
    all_items = order.items.all().select_related('product')
    
    for item in all_items:
        item_total = item.quantity * item.price_at_order
        name = item.product.name
        
        # Переводим числовые значения в строки для контролируемого выравнивания
        qty_str = f"{item.quantity}"
        price_str = f"{int(item.price_at_order)}"
        total_str = f"{int(item_total)}"
        
        # Если название слишком длинное — переносим его на отдельную строку,
        # чтобы цифры гарантированно остались в своих ровных колонках
        if len(name) > 13:
            lines.append(name)
            lines.append(f"{'':<14} {qty_str:<4} {price_str:<6} {total_str}")
        else:
            lines.append(f"{name:<14} {qty_str:<4} {price_str:<6} {total_str}")

    lines.append("----------------------------------")
    lines.append(f"ИТОГО К ОПЛАТЕ:      {int(order.total_amount)} сом")
    
    # Показываем метод оплаты только на финальном чеке
    if is_final and hasattr(order, 'payment_method') and order.payment_method:
        # Получаем понятное человеку название из choices (например, "Наличные 💵")
        payment_display = order.get_payment_method_display()
        lines.append(f"Способ оплаты:       {payment_display}")
        
    lines.append("==================================")
    lines.append("        Спасибо за визит!         ")
    lines.append("\n\n\n\n\n") # Прокрутка для удобного отрыва ленты
    
    return "\n".join(lines)


def send_to_bill_printer(order, is_final=False):
    """
    Печать клиентского чека. Генерирует полный текст и выводит его в лог/файл.
    """
    text = generate_bill_text(order, is_final)
    
    # Для отладки в терминале
    print(text)
    
    # Раскомментируйте этот блок, чтобы чеки сохранялись в файлы для проверки макета:
    # prefix = "final_bill" if is_final else "pre_bill"
    # with open(f"media/tickets/{prefix}_{order.id}.txt", "w", encoding="utf-8") as f:
    #     f.write(text)
        
    return True

# --- Функции-обертки для цехов ---

def send_to_grill_printer(order, grill_items):
    text = generate_ticket_text(order, grill_items, "Мангал 🔥")
    if text:
        print(text) # Пока выводим в консоль для тестов

def send_to_bar_printer(order, bar_items):
    text = generate_ticket_text(order, bar_items, "Бар 🍹")
    if text:
        print(text)

def send_to_kitchen_printer(order, kitchen_items):
    text = generate_ticket_text(order, kitchen_items, "Кухня 🍳")
    if text:
        print(text)