from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("web.apps.core.urls")),
    path("", include("web.apps.judging.urls")),  # Step 3 walking skeleton + Step 8
    path("", include("web.apps.candidate.urls")),  # Step 5 + Step 7 + Step 9
    path("", include("web.apps.interviewer.urls")),  # Step 10
]
