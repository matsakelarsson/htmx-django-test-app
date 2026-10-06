from urllib.parse import urlencode

from django import forms
from django.urls import reverse

INPUT_CLASSES = (
    "w-40 rounded-lg border border-slate-300 bg-white py-2.5 pr-10 pl-3 text-slate-900 "
    "placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30 "
    "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
)


class DatePickerInput(forms.DateInput):
    """A text input for an ISO date with a calendar popover rendered by the server.

    The browser's Popover API opens the calendar and htmx loads the month grid into it, so the
    widget ships no JavaScript. Use it on any date field::

        due_date = forms.DateField(widget=DatePickerInput())

    Picking a day re-renders the widget from its field name and id alone, so give the field a
    ``<label>`` rather than extra widget attrs, which a pick would not carry over.
    """

    template_name = "datepicker/widget.html"

    def __init__(self, attrs=None, *, focus_toggle=False):
        defaults = {"class": INPUT_CLASSES, "placeholder": "YYYY-MM-DD", "autocomplete": "off"}
        super().__init__(attrs={**defaults, **(attrs or {})}, format="%Y-%m-%d")
        # After a pick the old day button is gone, so the view asks for focus on the toggle.
        self.focus_toggle = focus_toggle

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_attrs = context["widget"]["attrs"]
        element_id = widget_attrs.setdefault("id", f"id_{name}")
        params = {"dp_field": name, "dp_id": element_id}
        if widget_attrs.get("required"):
            params["dp_required"] = "1"
        context["picker"] = {
            "id": element_id,
            "calendar_url": f"{reverse('datepicker:calendar')}?{urlencode(params)}",
            "focus_toggle": self.focus_toggle,
        }
        return context
