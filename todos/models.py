from django.db import models
from django.utils import timezone


class Todo(models.Model):
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Oldest first so the full-page render matches the order HTMX appends new items.
        ordering = ["created_at", "pk"]

    def __str__(self):
        return self.title

    @property
    def overdue(self):
        return self.due_date is not None and not self.done and self.due_date < timezone.localdate()


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)
    # Dropping a todo on a tag adds a row to this relation.
    todos = models.ManyToManyField(Todo, related_name="tags", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
