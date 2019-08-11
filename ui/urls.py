from django.urls import path

from . import views

urlpatterns = [
    path(r'manager', views.proxy_manager, name='ui_manager'),
    path(r'login', views.login_view, name='ui_login'),
]
