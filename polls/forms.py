from django import forms

from .models import Poll

MIN_OPTIONS = 2
MAX_OPTIONS = 5
OPTION_MAX_LENGTH = 80


class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = ("question", "description")
        labels = {
            "question": "Neye karar veremiyorsun?",
            "description": "Açıklama (isteğe bağlı)",
        }
        widgets = {
            "question": forms.TextInput(attrs={"maxlength": 140}),
            "description": forms.Textarea(attrs={"rows": 2, "maxlength": 280}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.option_values = self.data.getlist("option") if self.is_bound else []

    @property
    def display_option_values(self):
        values = self.option_values[:MAX_OPTIONS]
        return values + [""] * (MIN_OPTIONS - len(values))

    def clean(self):
        cleaned = super().clean()
        options = [value.strip() for value in self.option_values if value.strip()]

        if len(options) < MIN_OPTIONS:
            self.add_error(None, "En az 2 seçenek gerekli.")
        elif len(options) > MAX_OPTIONS:
            self.add_error(None, "En fazla 5 seçenek ekleyebilirsin.")
        if any(len(option) > OPTION_MAX_LENGTH for option in options):
            self.add_error(None, "Her seçenek en fazla 80 karakter olabilir.")
        if len({option.casefold() for option in options}) != len(options):
            self.add_error(None, "Aynı seçeneği iki kez ekleyemezsin.")

        cleaned["options"] = options
        return cleaned
