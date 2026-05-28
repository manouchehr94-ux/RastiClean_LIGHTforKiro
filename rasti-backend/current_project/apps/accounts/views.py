"""
Accounts - Views.

Thin views for authentication. All business logic delegated to services.
All permission logic uses decorators from permissions.py.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import PlatformLoginForm, TenantLoginForm
from .services import AuthenticationService, RedirectService


# =============================================================================
# PLATFORM AUTHENTICATION VIEWS
# =============================================================================


def platform_login(request: HttpRequest) -> HttpResponse:
    """
    Platform owner login page at /loginlogin/.

    GET: Display login form.
    POST: Authenticate platform owner, redirect to dashboard.
    """
    # Already logged in platform owner → redirect to dashboard
    if request.user.is_authenticated:
        from .permissions import is_platform_owner
        if is_platform_owner(request.user):
            return redirect("/loginlogin/dashboard/")

    error = ""
    form = PlatformLoginForm()

    if request.method == "POST":
        form = PlatformLoginForm(request.POST)
        if form.is_valid():
            user, error = AuthenticationService.authenticate_platform_user(
                request=request,
                phone=form.cleaned_data["phone"],
                password=form.cleaned_data["password"],
            )
            if user:
                AuthenticationService.login_user(request=request, user=user)
                return redirect("/loginlogin/dashboard/")

    return render(request, "accounts/platform_login.html", {
        "form": form,
        "error": error,
    })


def platform_logout(request: HttpRequest) -> HttpResponse:
    """Logout for platform owners."""
    AuthenticationService.logout_user(request=request)
    return redirect("/loginlogin/")


# =============================================================================
# TENANT AUTHENTICATION VIEWS
# =============================================================================


def tenant_login(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Tenant user login page at /<company_code>/login/.

    GET: Display login form for the company.
    POST: Authenticate user, enforce tenant isolation, redirect by role.

    Note: company_code kwarg comes from URL pattern but we use request.company
    (resolved by TenantMiddleware) instead.
    """
    company = getattr(request, "company", None)

    # Already logged in and belongs to this company → redirect
    if request.user.is_authenticated and company:
        from .permissions import user_belongs_to_company
        if user_belongs_to_company(request.user, company):
            url = RedirectService.get_post_login_url(
                user=request.user, company_code=company.code
            )
            return redirect(url)

    error = ""
    form = TenantLoginForm()

    if request.method == "POST":
        form = TenantLoginForm(request.POST)
        if form.is_valid():
            user, error = AuthenticationService.authenticate_tenant_user(
                request=request,
                phone=form.cleaned_data["phone"],
                password=form.cleaned_data["password"],
            )
            if user:
                AuthenticationService.login_user(request=request, user=user)
                url = RedirectService.get_post_login_url(
                    user=user, company_code=company.code
                )
                return redirect(url)

    return render(request, "accounts/tenant_login.html", {
        "form": form,
        "error": error,
        "company": company,
    })


def tenant_logout(request: HttpRequest, **kwargs) -> HttpResponse:
    """Logout for tenant users. Redirects back to company login."""
    company = getattr(request, "company", None)
    AuthenticationService.logout_user(request=request)
    if company:
        return redirect(f"/{company.code}/login/")
    return redirect("/")
