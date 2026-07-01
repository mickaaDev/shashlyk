from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('pos/', include('orders.urls')),  # Включает все представления официантов
    
    path('core/', include('core.urls')), 
    
    # Quick quality-of-life redirect: going to http://127.0.0.1:8000/ drops them straight into the dashboard
    path('', lambda request: redirect('waiter_dashboard', permanent=False)),
]