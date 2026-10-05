from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from .models import Tag, Todo

HX = {"HX-Request": "true"}


class IndexTests(TestCase):
    def test_renders_form_list_and_status(self):
        Todo.objects.create(title="Write tests")
        response = self.client.get(reverse("todos:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="todo-form"')
        self.assertContains(response, "Write tests")
        self.assertContains(response, "0 of 1 done")

    def test_empty_state(self):
        response = self.client.get(reverse("todos:index"))
        self.assertContains(response, "Nothing here yet")


class CreateTests(TestCase):
    def test_htmx_returns_item_plus_oob_status_and_form(self):
        response = self.client.post(reverse("todos:create"), {"title": "Buy milk"}, headers=HX)
        self.assertEqual(response.status_code, 200)
        todo = Todo.objects.get()
        self.assertEqual(todo.title, "Buy milk")
        self.assertContains(response, f'id="todo-{todo.pk}"')
        self.assertContains(response, 'id="todo-status" hx-swap-oob="true"')
        self.assertContains(response, "0 of 1 done")
        self.assertContains(response, 'id="todo-form"')
        self.assertContains(response, 'id="tag-list" hx-swap-oob="true"')
        self.assertContains(response, 'hx-swap-oob="true"', count=3)

    def test_htmx_blank_title_returns_form_with_error_and_creates_nothing(self):
        response = self.client.post(reverse("todos:create"), {"title": "   "}, headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Todo.objects.count(), 0)
        self.assertContains(response, 'id="todo-form"')
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "This field is required.")
        self.assertContains(response, 'aria-describedby="id_title_error"')
        self.assertContains(response, 'id="id_title_error"')
        self.assertNotContains(response, 'id="todo-status"')

    def test_plain_post_redirects(self):
        response = self.client.post(reverse("todos:create"), {"title": "Plain"})
        self.assertRedirects(response, reverse("todos:index"))
        self.assertTrue(Todo.objects.filter(title="Plain").exists())

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("todos:create")).status_code, 405)


class ToggleTests(TestCase):
    def test_flips_done_and_returns_item_with_oob_status(self):
        todo = Todo.objects.create(title="Toggle me")
        url = reverse("todos:toggle", args=[todo.pk])

        response = self.client.post(url, headers=HX)
        todo.refresh_from_db()
        self.assertTrue(todo.done)
        self.assertContains(response, "checked")
        self.assertContains(response, "line-through")
        self.assertContains(response, "1 of 1 done")
        self.assertContains(response, "Clear completed")

        response = self.client.post(url, headers=HX)
        todo.refresh_from_db()
        self.assertFalse(todo.done)
        self.assertNotContains(response, "line-through")
        self.assertNotContains(response, "Clear completed")

    def test_unknown_pk_404(self):
        self.assertEqual(self.client.post(reverse("todos:toggle", args=[999]), headers=HX).status_code, 404)


class DeleteTests(TestCase):
    def test_deletes_and_returns_only_oob_status(self):
        todo = Todo.objects.create(title="Remove me")
        response = self.client.delete(reverse("todos:delete", args=[todo.pk]), headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())
        self.assertContains(response, 'id="todo-status" hx-swap-oob="true"')
        self.assertNotContains(response, f'id="todo-{todo.pk}"')

    def test_post_not_allowed(self):
        todo = Todo.objects.create(title="Keep me")
        self.assertEqual(self.client.post(reverse("todos:delete", args=[todo.pk]), headers=HX).status_code, 405)
        self.assertTrue(Todo.objects.filter(pk=todo.pk).exists())


class ClearCompletedTests(TestCase):
    def test_removes_done_items_and_returns_fresh_list(self):
        keep = Todo.objects.create(title="Still open")
        Todo.objects.create(title="Finished", done=True)
        response = self.client.post(reverse("todos:clear_completed"), headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(Todo.objects.all(), [keep])
        self.assertContains(response, 'id="todo-list"')
        self.assertContains(response, "Still open")
        self.assertNotContains(response, "Finished")
        self.assertContains(response, "0 of 1 done")


class DragAndDropMarkupTests(TestCase):
    def test_rows_are_drag_sources_and_tags_are_drop_targets(self):
        todo = Todo.objects.create(title="Drag me")
        tag = Tag.objects.create(name="Work")
        response = self.client.get(reverse("todos:index"))
        # Source: draggable row that records its id in the shared hidden input.
        self.assertContains(response, f'id="todo-{todo.pk}" draggable="true" data-todo-id="{todo.pk}"')
        self.assertContains(response, '<input type="hidden" id="dragged-todo" name="todo">', html=True)
        # Target: posts on drop and submits that hidden input.
        self.assertContains(response, f'hx-post="{reverse("todos:tag_add_todo", args=[tag.pk])}"', count=2)
        self.assertContains(response, 'hx-trigger="drop"', count=1)
        self.assertContains(response, 'hx-include="#dragged-todo"', count=1)
        # Persistent live region for outcomes, empty on first render.
        self.assertContains(response, 'id="tag-status"')
        self.assertContains(response, 'role="status"')

    def test_no_template_comments_leak_into_the_page(self):
        todo = Todo.objects.create(title="Drag me")
        Tag.objects.create(name="Work").todos.add(todo)
        content = self.client.get(reverse("todos:index")).content.decode()
        self.assertNotIn("{#", content)
        self.assertNotIn("{%", content)


class TagCreateTests(TestCase):
    def test_htmx_returns_fresh_form_plus_oob_list_and_status(self):
        response = self.client.post(reverse("todos:tag_create"), {"name": "Work"}, headers=HX)
        self.assertEqual(response.status_code, 200)
        tag = Tag.objects.get()
        self.assertContains(response, 'id="tag-form"')
        self.assertContains(response, 'id="tag-list" hx-swap-oob="true"')
        self.assertContains(response, f'id="tag-{tag.pk}"')
        self.assertContains(response, 'id="tag-status"')
        self.assertContains(response, 'hx-swap-oob="innerHTML"')
        self.assertContains(response, "Created tag “Work”.")

    def test_htmx_duplicate_name_returns_422_with_only_the_form(self):
        Tag.objects.create(name="Work")
        response = self.client.post(reverse("todos:tag_create"), {"name": "Work"}, headers=HX)
        self.assertContains(response, 'role="alert"', status_code=422)
        self.assertContains(response, "already exists", status_code=422)
        self.assertNotContains(response, 'id="tag-list"', status_code=422)
        self.assertEqual(Tag.objects.count(), 1)

    def test_plain_post_redirects(self):
        response = self.client.post(reverse("todos:tag_create"), {"name": "Home"})
        self.assertRedirects(response, reverse("todos:index"))
        self.assertTrue(Tag.objects.filter(name="Home").exists())

    def test_plain_post_invalid_renders_full_page_with_error(self):
        response = self.client.post(reverse("todos:tag_create"), {"name": ""})
        self.assertContains(response, "<title>", status_code=422)
        self.assertContains(response, 'role="alert"', status_code=422)


class TagAddTodoTests(TestCase):
    """The endpoint behind both the drop target and the no-drag picker."""

    def setUp(self):
        self.tag = Tag.objects.create(name="Work")
        self.todo = Todo.objects.create(title="Write report")
        self.url = reverse("todos:tag_add_todo", args=[self.tag.pk])

    def test_htmx_adds_relation_and_returns_card_plus_status(self):
        response = self.client.post(self.url, {"todo": self.todo.pk}, headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(self.tag.todos.all(), [self.todo])
        self.assertContains(response, f'id="tag-{self.tag.pk}"')
        self.assertContains(response, "Write report")
        self.assertContains(response, "Added “Write report” to “Work”.")
        self.assertContains(response, 'hx-swap-oob="innerHTML"')
        # The response re-renders the drop target along with the card.
        self.assertContains(response, 'hx-trigger="drop"')
        # Nothing left to offer, so the picker is gone.
        self.assertNotContains(response, "<select")

    def test_picker_offers_only_todos_the_tag_lacks(self):
        other = Todo.objects.create(title="Other")
        self.tag.todos.add(self.todo)
        response = self.client.get(reverse("todos:index"))
        self.assertContains(response, f'<option value="{other.pk}">Other</option>', html=True)
        self.assertNotContains(response, f'<option value="{self.todo.pk}">')

    def test_adding_twice_keeps_one_relation_and_says_so(self):
        self.client.post(self.url, {"todo": self.todo.pk}, headers=HX)
        response = self.client.post(self.url, {"todo": self.todo.pk}, headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.tag.todos.count(), 1)
        self.assertContains(response, "“Write report” is already tagged “Work”.")

    def test_unknown_todo_returns_422_with_card_and_message(self):
        response = self.client.post(self.url, {"todo": 999}, headers=HX)
        self.assertContains(response, "That todo no longer exists.", status_code=422)
        self.assertContains(response, f'id="tag-{self.tag.pk}"', status_code=422)
        self.assertEqual(self.tag.todos.count(), 0)

    def test_missing_or_malformed_todo_returns_422(self):
        for payload, message in [
            ({}, "Choose a todo to add."),
            ({"todo": ""}, "Choose a todo to add."),
            ({"todo": "abc"}, "That todo no longer exists."),
        ]:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, headers=HX)
                self.assertContains(response, message, status_code=422)
        self.assertEqual(self.tag.todos.count(), 0)

    def test_unknown_tag_404(self):
        url = reverse("todos:tag_add_todo", args=[999])
        self.assertEqual(self.client.post(url, {"todo": self.todo.pk}, headers=HX).status_code, 404)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_plain_post_adds_and_redirects(self):
        response = self.client.post(self.url, {"todo": self.todo.pk})
        self.assertRedirects(response, reverse("todos:index"))
        self.assertQuerySetEqual(self.tag.todos.all(), [self.todo])


class TagRemoveTodoTests(TestCase):
    def setUp(self):
        self.tag = Tag.objects.create(name="Work")
        self.todo = Todo.objects.create(title="Write report")
        self.tag.todos.add(self.todo)
        self.url = reverse("todos:tag_remove_todo", args=[self.tag.pk, self.todo.pk])

    def test_removes_relation_keeps_todo_and_focuses_picker(self):
        response = self.client.delete(self.url, headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.tag.todos.count(), 0)
        self.assertTrue(Todo.objects.filter(pk=self.todo.pk).exists())
        self.assertContains(response, "Removed “Write report” from “Work”.")
        self.assertContains(response, f'<option value="{self.todo.pk}">Write report</option>', html=True)
        self.assertContains(response, "autofocus")

    def test_removing_twice_is_harmless(self):
        self.client.delete(self.url, headers=HX)
        response = self.client.delete(self.url, headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Removed")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(self.url, headers=HX).status_code, 405)
        self.assertEqual(self.tag.todos.count(), 1)


class TagDeleteTests(TestCase):
    def test_deletes_tag_keeps_its_todos_and_returns_list(self):
        tag = Tag.objects.create(name="Work")
        todo = Todo.objects.create(title="Write report")
        tag.todos.add(todo)
        response = self.client.delete(reverse("todos:tag_delete", args=[tag.pk]), headers=HX)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tag.objects.exists())
        self.assertTrue(Todo.objects.filter(pk=todo.pk).exists())
        self.assertContains(response, 'id="tag-list"')
        self.assertContains(response, "No tags yet")
        self.assertContains(response, "Deleted tag “Work”.")


class TagCardsStayFreshTests(TestCase):
    """Views that change the set of todos refresh the tag cards out of band."""

    def setUp(self):
        self.tag = Tag.objects.create(name="Work")

    def test_new_todo_appears_in_pickers(self):
        response = self.client.post(reverse("todos:create"), {"title": "Fresh"}, headers=HX)
        todo = Todo.objects.get()
        self.assertContains(response, 'id="tag-list" hx-swap-oob="true"')
        self.assertContains(response, f'<option value="{todo.pk}">Fresh</option>', html=True)

    def test_deleted_todo_leaves_tag_cards(self):
        todo = Todo.objects.create(title="Short lived")
        self.tag.todos.add(todo)
        response = self.client.delete(reverse("todos:delete", args=[todo.pk]), headers=HX)
        self.assertContains(response, 'id="tag-list" hx-swap-oob="true"')
        self.assertNotContains(response, "Short lived")

    def test_cleared_todos_leave_tag_cards(self):
        todo = Todo.objects.create(title="Finished", done=True)
        self.tag.todos.add(todo)
        response = self.client.post(reverse("todos:clear_completed"), headers=HX)
        self.assertContains(response, 'id="tag-list" hx-swap-oob="true"')
        self.assertNotContains(response, "Finished")


class HtmxScriptTests(TestCase):
    def test_htmx_is_the_only_script_and_is_served_locally(self):
        content = self.client.get(reverse("todos:index")).content.decode()
        self.assertIn('<script src="/static/django_htmx/htmx-2.min.js" defer></script>', content)
        self.assertEqual(content.count("<script"), 1)
        self.assertNotIn("cdn.", content)

    def test_bundled_htmx_file_exists(self):
        # Fails loudly if a django-htmx upgrade renames the bundled file.
        self.assertIsNotNone(finders.find("django_htmx/htmx-2.min.js"))
