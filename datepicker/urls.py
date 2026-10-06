from django.urls import path

from . import views

app_name = "datepicker"

urlpatterns = [
    path("calendar/", views.calendar, name="calendar"),
    path("pick/", views.pick, name="pick"),
]
