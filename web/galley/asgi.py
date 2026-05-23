"""
ASGI entrypoint with Channels WebSocket routing (Step 7).

- HTTP: Django's normal request/response cycle.
- WebSocket: candidate snapshot ingest + interviewer observe.
"""
import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.galley.settings")
django.setup()

django_asgi_app = get_asgi_application()

# Late import — must happen after django.setup()
from web.apps.candidate.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
