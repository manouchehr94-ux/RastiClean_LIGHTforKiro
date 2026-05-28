"""
Invoices - Technician URLs.

Served under /<company_code>/tech/invoices/.
Technicians can view invoices for their assigned orders.
"""
from django.urls import path

from . import views_technician

app_name = "invoices_technician"

urlpatterns = [
    path("", views_technician.technician_invoice_list, name="list"),
    path("<int:invoice_id>/", views_technician.technician_invoice_detail, name="detail"),
]
