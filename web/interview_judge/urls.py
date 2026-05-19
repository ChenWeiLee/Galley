from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("web.apps.core.urls")),
    path("", include("web.apps.judging.urls")),  # Step 3 walking skeleton + Step 8
    path("", include("web.apps.candidate.urls")),  # Step 5 + Step 7 + Step 9
    path("", include("web.apps.interviewer.urls")),  # Step 10
]

# In DEBUG mode Daphne doesn't auto-serve static files (that's a runserver
# trick); add an explicit handler so dev works on :8000. Production goes
# through nginx (:80) which serves /static/ directly from disk.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Also serve from STATICFILES_DIRS so we don't need collectstatic in dev.
    for d in settings.STATICFILES_DIRS:
        urlpatterns += static(settings.STATIC_URL, document_root=str(d))
