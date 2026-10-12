from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import RegisterForm

CREATE_POLL_PATH = "/anket/olustur/"


def register(request):
    if request.user.is_authenticated:
        return redirect("/")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Hoş geldin, @{user.username}")
        return redirect("/")
    return render(request, "accounts/register.html", {"form": form})


class SiteLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_create_notice"] = self.request.GET.get("next") == CREATE_POLL_PATH
        return context
