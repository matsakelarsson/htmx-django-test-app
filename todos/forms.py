from django import forms

from datepicker.widgets import DatePickerInput

from .models import Tag, Todo

INPUT_CLASSES = (
    "min-w-56 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 "
    "placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30 "
    "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
)


class TodoForm(forms.ModelForm):
    # Let empty submits reach the server so the HTMX validation-error flow is exercised.
    use_required_attribute = False

    class Meta:
        model = Todo
        fields = ["title", "due_date"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "placeholder": "What needs doing?",
                    "autocomplete": "off",
                    "autofocus": True,
                    "aria-label": "New todo",
                }
            ),
            "due_date": DatePickerInput(),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "placeholder": "New tag",
                    "autocomplete": "off",
                    "aria-label": "New tag",
                }
            )
        }


class AddTodoForm(forms.Form):
    """Validates the todo sent by a drop or by a tag's picker."""

    todo = forms.ModelChoiceField(
        queryset=Todo.objects.all(),
        error_messages={
            "required": "Choose a todo to add.",
            "invalid_choice": "That todo no longer exists.",
        },
    )
