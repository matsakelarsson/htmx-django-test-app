from django.db import models


class Todo(models.Model):
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Oldest first so the full-page render matches the order HTMX appends new items.
        ordering = ["created_at", "pk"]

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)
    # Dropping a todo on a tag adds a row to this relation.
    todos = models.ManyToManyField(Todo, related_name="tags", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
