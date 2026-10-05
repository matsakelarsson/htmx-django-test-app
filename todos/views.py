from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST

from .forms import AddTodoForm, TagForm, TodoForm
from .models import Tag, Todo

PARTIALS = "todos/partials/"


def status_context():
    todos = Todo.objects.all()
    return {"total": todos.count(), "done": todos.filter(done=True).count()}


def tag_cards(tags=None):
    """Describe each tag card: the todos it holds and the ones its picker can still offer."""
    if tags is None:
        tags = Tag.objects.prefetch_related("todos")
    all_todos = list(Todo.objects.all())
    cards = []
    for tag in tags:
        members = list(tag.todos.all())
        member_ids = {todo.pk for todo in members}
        cards.append(
            {
                "tag": tag,
                "todos": members,
                "available": [todo for todo in all_todos if todo.pk not in member_ids],
            }
        )
    return cards


def page_context(**overrides):
    return {
        "todos": Todo.objects.all(),
        "form": TodoForm(),
        "tag_form": TagForm(),
        "cards": tag_cards(),
        **status_context(),
        **overrides,
    }


def htmx_response(request, *parts, status=200):
    """Join rendered partials into one response.

    The first part is what HTMX swaps into the target; parts rendered with
    ``oob=True`` carry ``hx-swap-oob`` and update other regions of the page.
    """
    html = "".join(render_to_string(PARTIALS + name, ctx, request) for name, ctx in parts)
    return HttpResponse(html, status=status)


def tag_list_oob():
    """Tag cards list todo titles, so refresh them whenever the set of todos changes."""
    return ("_tag_list.html", {"cards": tag_cards(), "oob": True})


def tag_status_oob(message):
    """Fill the persistent status region so the outcome is visible and announced."""
    return ("_tag_status.html", {"message": message, "oob": True})


def index(request):
    return render(request, "todos/index.html", page_context())


@require_POST
def create(request):
    form = TodoForm(request.POST)
    if not form.is_valid():
        if not request.htmx:
            return render(request, "todos/index.html", page_context(form=form))
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
        tag_list_oob(),
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
    # The button uses hx-swap="delete", so only out-of-band parts are needed.
    return htmx_response(
        request,
        ("_status.html", {**status_context(), "oob": True}),
        tag_list_oob(),
    )


@require_POST
def clear_completed(request):
    Todo.objects.filter(done=True).delete()
    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_list.html", {"todos": Todo.objects.all()}),
        ("_status.html", {**status_context(), "oob": True}),
        tag_list_oob(),
    )


@require_POST
def tag_create(request):
    form = TagForm(request.POST)
    if not form.is_valid():
        if not request.htmx:
            return render(request, "todos/index.html", page_context(tag_form=form), status=422)
        return htmx_response(request, ("_tag_form.html", {"tag_form": form}), status=422)

    tag = form.save()
    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_tag_form.html", {"tag_form": TagForm()}),
        tag_list_oob(),
        tag_status_oob(f"Created tag “{tag.name}”."),
    )


@require_http_methods(["DELETE"])
def tag_delete(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    tag.delete()
    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_tag_list.html", {"cards": tag_cards()}),
        tag_status_oob(f"Deleted tag “{tag.name}”."),
    )


@require_POST
def tag_add_todo(request, pk):
    """Attach a todo to a tag. Serves both the drop target and the no-drag picker."""
    tag = get_object_or_404(Tag, pk=pk)
    form = AddTodoForm(request.POST)
    status = 200
    if form.is_valid():
        todo = form.cleaned_data["todo"]
        if tag.todos.filter(pk=todo.pk).exists():
            message = f"“{todo.title}” is already tagged “{tag.name}”."
        else:
            tag.todos.add(todo)
            message = f"Added “{todo.title}” to “{tag.name}”."
    else:
        message = form.errors["todo"][0]
        status = 422

    if not request.htmx:
        return redirect("todos:index")
    return htmx_response(
        request,
        ("_tag.html", {"card": tag_cards([tag])[0]}),
        tag_status_oob(message),
        status=status,
    )


@require_http_methods(["DELETE"])
def tag_remove_todo(request, pk, todo_pk):
    tag = get_object_or_404(Tag, pk=pk)
    todo = tag.todos.filter(pk=todo_pk).first()
    message = ""
    if todo is not None:
        tag.todos.remove(todo)
        message = f"Removed “{todo.title}” from “{tag.name}”."
    if not request.htmx:
        return redirect("todos:index")
    # The clicked button is gone after the swap, so move focus to the card's picker.
    return htmx_response(
        request,
        ("_tag.html", {"card": tag_cards([tag])[0], "focus_picker": True}),
        tag_status_oob(message),
    )
