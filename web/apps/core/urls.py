from django.urls import path

from . import healthz

urlpatterns = [
    path("healthz", healthz.healthz, name="healthz"),
    path("readyz", healthz.readyz, name="readyz"),
]
