from django.test import TestCase
from django.urls import reverse

from .models import Todo

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
        self.assertContains(response, 'hx-swap-oob="true"', count=2)

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
