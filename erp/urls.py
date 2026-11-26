from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('upload/', views.upload_po, name='upload_po'),
    path('ship/<int:po_id>/', views.ship_order, name='ship_order'),
    path('update-stock/', views.update_stock, name='update_stock'),
    path('orders/', views.orders_detail, name='orders_detail'),
]