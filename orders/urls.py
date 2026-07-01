from django.urls import path
from . import views

# Wire these directly to your main config setup
urlpatterns = [
    path('dashboard/', views.waiter_dashboard, name='waiter_dashboard'),
    path('table/<int:table_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/add/<int:product_id>/', views.add_item_to_order, name='add_item_to_order'),
    path('item/<int:item_id>/increase/', views.increase_item, name='increase_item'),
    path('item/<int:item_id>/decrease/', views.decrease_item, name='decrease_item'),
    path('order/<int:order_id>/send/', views.send_order_to_kitchen, name='send_order_to_kitchen'),
    path('item/<int:item_id>/resend/', views.resend_item_to_kitchen, name='resend_item_to_kitchen'),
    path('order/<int:order_id>/close/', views.close_order, name='close_order'),
    path('order/<int:order_id>/bill/', views.view_bill, name='view_bill'),
]