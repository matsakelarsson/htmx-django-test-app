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
