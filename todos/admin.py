from django.contrib import admin

from .models import Todo


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ("title", "done", "created_at")
    list_filter = ("done",)
    search_fields = ("title",)
