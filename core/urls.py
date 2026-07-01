from django.urls import path
from . import views

urlpatterns = [
    # ... ваши другие пути для приложения core ...
    path('management/shift/', views.shift_management, name='shift_management'),
    path('management/shift/toggle/', views.toggle_shift, name='toggle_shift'),
]