"""
Health endpoints — Patch #5 / Plan REV-5.

- /healthz: liveness — returns 200 as long as the process can serve.
  Used by docker-compose healthcheck and load balancer.
- /readyz: readiness — returns 200 only when DB + redis-channels + Judge0
  all reachable. Used to gate traffic during deploys.
"""
import httpx
from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness — process is alive and serving."""
    return JsonResponse({"status": "ok"})


def readyz(request):
    """Readiness — all hard dependencies reachable. Returns 503 on any failure."""
    checks: dict[str, str] = {}

    # DB
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        checks["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["db"] = f"fail: {e.__class__.__name__}"

    # Channels redis (light ping via channel layer)
    try:
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        # The channel layer doesn't expose a ping; do a no-op group_add/discard.
        # If unreachable, this raises.
        import asyncio

        async def _probe():
            await layer.group_add("__healthz__", "__probe__")
            await layer.group_discard("__healthz__", "__probe__")

        asyncio.run(_probe())
        checks["redis_channels"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["redis_channels"] = f"fail: {e.__class__.__name__}"

    # Judge0
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{settings.JUDGE0_BASE_URL}/about")
            checks["judge0"] = "ok" if r.status_code == 200 else f"fail: HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        checks["judge0"] = f"fail: {e.__class__.__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if all_ok else "degraded", "checks": checks},
                        status=200 if all_ok else 503)
