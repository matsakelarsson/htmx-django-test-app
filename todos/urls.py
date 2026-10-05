from django.urls import path

from . import views

app_name = "todos"

urlpatterns = [
    path("", views.index, name="index"),
    path("todos/", views.create, name="create"),
    path("todos/<int:pk>/toggle/", views.toggle, name="toggle"),
    path("todos/<int:pk>/", views.delete, name="delete"),
    path("todos/clear-completed/", views.clear_completed, name="clear_completed"),
    path("tags/", views.tag_create, name="tag_create"),
    path("tags/<int:pk>/", views.tag_delete, name="tag_delete"),
    path("tags/<int:pk>/todos/", views.tag_add_todo, name="tag_add_todo"),
    path("tags/<int:pk>/todos/<int:todo_pk>/", views.tag_remove_todo, name="tag_remove_todo"),
]
