from django.db import models
from django.utils import timezone

class Material(models.Model):
    name = models.CharField(max_length=200)
    current_stock = models.IntegerField(default=0)
    unit = models.CharField(max_length=50, default="Units")

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    po_number = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=200, default="Unknown Customer")
    order_date = models.DateField(default=timezone.now)
    delivery_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default="Pending")
    stock_allocated = models.BooleanField(default=False)
    date_received = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.po_number

class OrderItem(models.Model):
    """Links specific materials and quantities to a Purchase Order"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.quantity}x {self.material.name} for {self.purchase_order.po_number}"