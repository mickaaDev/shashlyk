from django.utils import timezone

def generate_ticket_text(order, items, department_name):
    """
    Базовый генератор текста встречки.
    items: отфильтрованный QuerySet с блюдами конкретного цеха
    """
    if not items.exists():
        return None

    # 1. Шапка встречки
    lines = []
    lines.append("==================================")
    lines.append(f"   ВСТРЕЧКА: {department_name.upper()}")
    lines.append("==================================")
    lines.append(f"Чек: #{order.id}")
    lines.append(f"Стол: №{order.table.number}")
    lines.append(f"Официант: {order.waiter.username}")
    lines.append(f"Время: {timezone.now().strftime('%H:%M:%S')}")
    lines.append("----------------------------------")
    
    # 2. Список блюд цеха
    for item in items:
        # Форматируем строку: Название блюда x Количество
        lines.append(f"{item.product.name:<24} x {item.quantity}")
        if item.comment: # Если официант оставил комментарий (например, "без лука")
            lines.append(f"  * ЛОГ: {item.comment}")
            
    lines.append("----------------------------------")
    lines.append("\n\n\n\n\n") # Прокрутка ленты, чтобы повару было удобно отрезать
    
    # Объединяем все строки через перенос строки
    return "\n".join(lines)


# 🌟 Функции-обертки для каждого цеха:

def send_to_grill_printer(order, grill_items):
    text = generate_ticket_text(order, grill_items, "Мангал 🔥")
    if text:
        # Здесь логика отправки на принтер мангала. 
        # Например, запись в файл, отправка по TCP/IP или через python-escpos
        with open(f"media/tickets/grill_order_{order.id}.txt", "w", encoding="utf-8") as f:
            f.write(text)

def send_to_bar_printer(order, bar_items):
    text = generate_ticket_text(order, bar_items, "Бар 🍹")
    if text:
        with open(f"media/tickets/bar_order_{order.id}.txt", "w", encoding="utf-8") as f:
            f.write(text)

def send_to_kitchen_printer(order, kitchen_items):
    text = generate_ticket_text(order, kitchen_items, "Кухня 🍳")
    if text:
        with open(f"media/tickets/kitchen_order_{order.id}.txt", "w", encoding="utf-8") as f:
            f.write(text)