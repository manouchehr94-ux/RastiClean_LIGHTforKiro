"""
Public - Views.

Public-facing marketing/informational pages.
No authentication required.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Landing page at /."""
    return render(request, "public/home.html")


def features(request: HttpRequest) -> HttpResponse:
    """Features page at /features/."""
    return render(request, "public/features.html")


def pricing(request: HttpRequest) -> HttpResponse:
    """Pricing page at /pricing/."""
    return render(request, "public/pricing.html")


def about(request: HttpRequest) -> HttpResponse:
    """About page at /about/."""
    return render(request, "public/about.html")


def contact(request: HttpRequest) -> HttpResponse:
    """Contact page at /contact/."""
    return render(request, "public/contact.html")


def register(request: HttpRequest) -> HttpResponse:
    """Company registration form at /register/."""
    return render(request, "public/register.html")


def register_verify(request: HttpRequest) -> HttpResponse:
    """Registration verification at /register/verify/."""
    return render(request, "public/register_verify.html")


def register_success(request: HttpRequest) -> HttpResponse:
    """Registration success at /register/success/."""
    return render(request, "public/register_success.html")
