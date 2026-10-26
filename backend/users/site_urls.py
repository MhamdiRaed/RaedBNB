from django.urls import path

from . import page_views


app_name = "site"

urlpatterns = [
    path("", page_views.home, name="home"),
    path("explore/", page_views.explore, name="explore"),
    path("about/", page_views.about, name="about"),
    path("contact/", page_views.contact, name="contact"),
    path("login/", page_views.sign_in, name="login"),
    path("register/", page_views.register, name="register"),
    path("logout/", page_views.sign_out, name="logout"),
    path("add-property/", page_views.add_property, name="add-property"),
]
