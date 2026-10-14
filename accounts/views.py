from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from polls.ratelimit import get_client_ip, is_rate_limited
from .forms import RegisterForm

CREATE_POLL_PATH = "/anket/olustur/"


def register(request):
    if request.user.is_authenticated:
        return redirect("/")

    ip = get_client_ip(request)
    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if is_rate_limited(f"register:{ip}", limit=10, period=60):
            form.add_error(None, "Çok fazla kayıt isteği gönderdin. Lütfen bir süre sonra tekrar dene.")
        elif form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Hoş geldin, @{user.username}")
            return redirect("/")
    return render(request, "accounts/register.html", {"form": form})


class SiteLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        if is_rate_limited(f"login:{ip}", limit=20, period=60):
            form = self.get_form()
            form.add_error(None, "Çok fazla giriş denemesi yapıldı. Lütfen biraz sonra tekrar dene.")
            return self.render_to_response(self.get_context_data(form=form))
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_create_notice"] = self.request.GET.get("next") == CREATE_POLL_PATH
        return context
