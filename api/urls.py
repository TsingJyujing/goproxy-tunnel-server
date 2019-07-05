from django.urls import path

from . import views

urlpatterns = [
    path(r'list', views.get_proxy_list, name='list'),
    path(r'create', views.create_tunnel, name='create'),
    path(r'remove', views.remove_tunnel, name='remove'),
    path(r'heartbeat', views.tunnel_heartbeat, name='heartbeat'),
    path(r'query', views.query_tunnel, name='query'),
]
