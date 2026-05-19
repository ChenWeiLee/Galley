"""Channels routing for candidate + observer sockets."""
from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/candidate/<str:session_id>/", consumers.CandidateConsumer.as_asgi()),
    path("ws/observe/<str:session_id>/", consumers.ObserverConsumer.as_asgi()),
]
