import re
import datetime
from PIL import Image
import pytesseract
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import PurchaseOrder, Material, OrderItem

# Point Python directly to your local Tesseract Engine
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


@login_required(login_url='login')
def dashboard(request):
    """Enterprise Dashboard Suite: Calculates KPIs and maps out Demand vs Allocation charts."""
    orders = PurchaseOrder.objects.all()
    materials = Material.objects.all()

    total_orders_count = orders.count()
    pending_requests = orders.filter(status='Pending').count()
    in_progress_requests = orders.filter(status='In Progress').count() 
    completed_requests = orders.filter(status__in=['Done', 'Shipped']).count()
    
    total_materials_count = materials.count()
    low_stock_count = materials.filter(current_stock__lt=20).count()

    # Timeline Throughput (Last 6 Months)
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    dummy_monthly_orders = [12, 18, 15, 22, 19, 0]
    
    po_by_month = PurchaseOrder.objects.annotate(month_idx=TruncMonth('date_received')) \
                                       .values('month_idx') \
                                       .annotate(count=Count('id')) \
                                       .order_by('month_idx')

    real_orders_map = defaultdict(int)
    for entry in po_by_month:
        if entry['month_idx']:
            m_name = entry['month_idx'].strftime('%b')
            real_orders_map[m_name] = entry['count']

    monthly_orders_data = []
    for i, month in enumerate(months_labels):
        has_real_order = real_orders_map[month]
        monthly_orders_data.append(has_real_order if has_real_order > 0 or month == 'Jun' else dummy_monthly_orders[i])

    # Dynamic Material Allocation Mapping
    chart_material_names = []
    stock_levels_data = []
    demand_levels_data = []

    for item in materials:
        chart_material_names.append(item.name)
        stock_levels_data.append(item.current_stock)
        
        active_demand = OrderItem.objects.filter(
            material_id=item.id,
            purchase_order__status__in=['Pending', 'In Progress']
        ).aggregate(total_demand=Sum('quantity'))['total_demand']

        # Ensure None balances revert cleanly back to an integer zero
        if active_demand is None:
            active_demand = 0
            
        demand_levels_data.append(active_demand)
    if not chart_material_names:
        chart_material_names = ['Steel Pipe', 'Copper Wire', 'Aluminium Sheets']
        stock_levels_data = [40, 120, 15]
        demand_levels_data = [0, 0, 0]

    # AI Runways Optimization Engine
    material_names = []
    days_left_data = []
    bar_colors = []
    ai_alerts = []
    
    for item in materials:
        avg_daily_usage = 5 
        days_left = item.current_stock // avg_daily_usage if avg_daily_usage > 0 else 0
        
        material_names.append(item.name)
        days_left_data.append(days_left)
        bar_colors.append('#dc3545' if days_left < 3 else '#198754')

        if days_left < 4:
            suggested_reorder = (avg_daily_usage * 14) - item.current_stock
            ai_alerts.append({
                'material': item.name,
                'days_left': days_left,
                'severity': 'danger' if days_left < 2 else 'warning',
                'action': f"Order minimum {max(suggested_reorder, 50)} units immediately to secure a 14-day production runway cycle."
            })

    return render(request, 'erp/dashboard.html', {
        'orders': orders.order_by('-date_received')[:5], 
        'materials': materials,
        'total_orders': total_orders_count,
        'pending_requests': pending_requests,
        'in_progress_requests': in_progress_requests,
        'completed_requests': completed_requests,
        'total_materials': total_materials_count,
        'low_stock_materials': low_stock_count,
        'pending_count': pending_requests,
        'in_progress_count': in_progress_requests,
        'shipped_count': completed_requests,
        'material_names': material_names,
        'days_left_data': days_left_data,
        'bar_colors': bar_colors,
        'months_labels': months_labels,
        'monthly_orders': monthly_orders_data,
        'chart_material_names': chart_material_names,
        'stock_levels_data': stock_levels_data,
        'demand_levels_data': demand_levels_data,
        'ai_alerts': ai_alerts,
    })

@login_required(login_url='login')
def upload_po(request):

    if request.method == "POST":
        action = request.POST.get("action")

        # ==========================================
        # ALLOCATE MATERIALS & SHIP ORDER
        # ==========================================
        if action == "allocate_materials":

            po_id = request.POST.get("po_id")
            po_record = get_object_or_404(PurchaseOrder, id=po_id)

            order_items = OrderItem.objects.filter(
                purchase_order=po_record
            )

            # Verify stock first
            for item in order_items:

                if item.material.current_stock < item.quantity:

                    messages.error(
                        request,
                        f"Insufficient stock for "
                        f"{item.material.name}. "
                        f"Required {item.quantity}, "
                        f"Available {item.material.current_stock}"
                    )

                    return redirect("upload_po")

            # Deduct stock
            for item in order_items:

                material = item.material
                material.current_stock -= item.quantity
                material.save()

            po_record.status = "Done"
            po_record.stock_allocated = True
            po_record.save()

            messages.success(
                request,
                f"{po_record.po_number} successfully allocated and shipped."
            )

            return redirect("upload_po")

        # ==========================================
        # STATUS UPDATE
        # ==========================================
        elif action == "update_status":

            po_id = request.POST.get("po_id")
            new_status = request.POST.get("status")

            po_record = get_object_or_404(
                PurchaseOrder,
                id=po_id
            )

            if new_status == "In Progress":

                order_items = OrderItem.objects.filter(
                    purchase_order=po_record
                )

                for item in order_items:

                    if item.material.current_stock < item.quantity:

                        messages.error(
                            request,
                            f"Cannot move order "
                            f"{po_record.po_number} "
                            f"to In Progress. "
                            f"{item.material.name} "
                            f"stock is insufficient."
                        )

                        return redirect("upload_po")

                po_record.status = "In Progress"
                po_record.save()

                messages.success(
                    request,
                    f"{po_record.po_number} moved to In Progress."
                )

                return redirect("upload_po")

            else:

                po_record.status = new_status
                po_record.save()

                messages.success(
                    request,
                    f"{po_record.po_number} updated to {new_status}."
                )

                return redirect("upload_po")

        # ==========================================
        # OCR FILE UPLOAD
        # ==========================================
        elif action == "upload_file":

            uploaded_file = request.FILES.get("po_document")

            if uploaded_file:

                img = Image.open(uploaded_file)

                extracted_text = pytesseract.image_to_string(img)
                print("\n" + "="*50)
                print("OCR EXTRACTED TEXT")
                print("="*50)
                print(extracted_text)
                print("="*50 + "\n")
                text_upper = extracted_text.upper()

                po_match = re.search(
                    r"BPCL[ \-_:.]*(\d+)",
                    text_upper
                )

                if po_match:

                    digits = po_match.group(1)
                    
                    final_po_number = f"BPCL-{digits}"
                    print("Detected PO Number:", final_po_number)
                else:

                    final_po_number = (
                        f"PENDING-{int(timezone.now().timestamp())}"
                    )

                po_record, created = PurchaseOrder.objects.get_or_create(
                    po_number=final_po_number,
                    defaults={"status": "Pending"}
                )

                if not created:

                    messages.warning(
                        request,
                        f"{final_po_number} already exists."
                    )

                    return redirect("upload_po")

                all_materials = Material.objects.all()

                detected_any_items = False

                for material in all_materials:

                    mat_name_upper = material.name.upper()

                    pattern = (
                        re.escape(mat_name_upper)
                        + r"[ \-_.:A-Z]*(\d+)"
                    )

                    item_match = re.search(
                        pattern,
                        text_upper
                    )

                    if item_match:

                        qty = int(item_match.group(1))

                        OrderItem.objects.create(
                            purchase_order=po_record,
                            material=material,
                            quantity=qty,
                            unit_price=0
                        )

                        detected_any_items = True

                if detected_any_items:

                    messages.success(
                        request,
                        f"{final_po_number} uploaded successfully."
                    )

                else:

                    messages.warning(
                        request,
                        f"{final_po_number} uploaded but "
                        f"no materials detected."
                    )

                return redirect("upload_po")

    purchase_orders = PurchaseOrder.objects.prefetch_related(
        "items__material"
    ).order_by("-date_received")

    return render(
        request,
        "erp/upload_po.html",
        {
            "purchase_orders": purchase_orders
        }
    )

@login_required(login_url='login')
def ship_order(request, po_id):
    """Warehouse Fulfillment Core: Officially closes records and deducts line item values from inventory stock."""
    order = get_object_or_404(PurchaseOrder, id=po_id)
    
    if order.status != 'Done' and order.status != 'Shipped':
        order.status = 'Done'
        order.save()
        
        requirements = OrderItem.objects.filter(purchase_order=order)
        
        deducted_items = []
        for req in requirements:
            material = req.material
            material.current_stock -= req.quantity
            material.save()
            deducted_items.append(f"{req.quantity} {material.unit} of {material.name}")
        
        if deducted_items:
            messages.success(request, f"Order {order.po_number} completed successfully! Stock allocations deducted: {', '.join(deducted_items)}.")
        else:
            messages.info(request, f"Order {order.po_number} marked 'Done'. No associated warehouse line items were detected.")
            
    return redirect('upload_po')


@login_required(login_url='login')
def update_stock(request):
    """Inventory Management Module: Handles incrementing stock levels and onboarding catalog records."""
    if request.method == "POST":
        action = request.POST.get('action')
        
        if action == "add_stock":
            mat_id = request.POST.get('material_id')
            added_qty = int(request.POST.get('new_quantity', 0))
            
            material = get_object_or_404(Material, id=mat_id)
            material.current_stock += added_qty
            material.save()
            messages.success(request, f"Successfully added {added_qty} {material.unit} to {material.name} stock.")
            
        elif action == "new_material":
            mat_name = request.POST.get('material_name').strip()
            initial_stock = int(request.POST.get('initial_stock', 0))
            unit_type = request.POST.get('unit_type', 'Units').strip()
            
            material, created = Material.objects.get_or_create(
                name__iexact=mat_name,
                defaults={'name': mat_name, 'current_stock': initial_stock, 'unit': unit_type}
            )
            
            if created:
                messages.success(request, f"New raw material tracking card '{mat_name}' established successfully.")
            else:
                messages.warning(request, f"Resource tracking card '{mat_name}' already exists.")
                
        return redirect('update_stock')
    
    materials = Material.objects.all().order_by('name')
    return render(request, 'erp/update_stock.html', {'materials': materials})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'erp/login.html', {'error': 'Invalid credentials. Please try again.'})
    return render(request, 'erp/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def orders_detail(request):
    orders = PurchaseOrder.objects.all().order_by('-date_received')
    return render(request, 'erp/orders_detail.html', {'orders': orders})