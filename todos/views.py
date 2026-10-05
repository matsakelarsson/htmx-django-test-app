from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST

from .forms import TodoForm
from .models import Todo

PARTIALS = "todos/partials/"


def status_context():
    todos = Todo.objects.all()
    return {"total": todos.count(), "done": todos.filter(done=True).count()}


def htmx_response(request, *parts):
    """Join rendered partials into one response.

    The first part is what HTMX swaps into the target; parts rendered with
    ``oob=True`` carry ``hx-swap-oob`` and update other regions of the page.
    """
    html = "".join(render_to_string(PARTIALS + name, ctx, request) for name, ctx in parts)
    return HttpResponse(html)


def index(request):
    return render(
        request,
        "todos/index.html",
        {"todos": Todo.objects.all(), "form": TodoForm(), **status_context()},
    )


@require_POST
def create(request):
    form = TodoForm(request.POST)
    if not form.is_valid():
        if not request.htmx:
            return render(
                request,
                "todos/index.html",
                {"todos": Todo.objects.all(), "form": form, **status_context()},
            )
        # Nothing for the main target; re-render the form with errors out of band.
        return htmx_response(request, ("_form.html", {"form": form, "oob": True}))

    todo = form.save()
    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_item.html", {"todo": todo}),
        ("_status.html", {**status_context(), "oob": True}),
        ("_form.html", {"form": TodoForm(), "oob": True}),
    )


@require_POST
def toggle(request, pk):
    todo = get_object_or_404(Todo, pk=pk)
    todo.done = not todo.done
    todo.save(update_fields=["done"])
    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_item.html", {"todo": todo}),
        ("_status.html", {**status_context(), "oob": True}),
    )


@require_http_methods(["DELETE"])
def delete(request, pk):
    get_object_or_404(Todo, pk=pk).delete()
    if not request.htmx:
        return redirect("todos:index")
    # The button uses hx-swap="delete", so only the out-of-band status is needed.
    return htmx_response(request, ("_status.html", {**status_context(), "oob": True}))


@require_POST
def clear_completed(request):
    Todo.objects.filter(done=True).delete()
    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_list.html", {"todos": Todo.objects.all()}),
        ("_status.html", {**status_context(), "oob": True}),
    )
