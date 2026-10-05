from django.urls import path

from . import views

app_name = "todos"

urlpatterns = [
    path("", views.index, name="index"),
    path("todos/", views.create, name="create"),
    path("todos/<int:pk>/toggle/", views.toggle, name="toggle"),
    path("todos/<int:pk>/", views.delete, name="delete"),
    path("todos/clear-completed/", views.clear_completed, name="clear_completed"),
]
