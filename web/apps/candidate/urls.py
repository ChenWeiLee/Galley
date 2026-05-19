from django.urls import path

from . import anticheat, views

app_name = "candidate"

urlpatterns = [
    path("t/<str:token>/", views.consume_token, name="consume_token"),
    path("enter/<str:token>/", views.consume_reentry, name="consume_reentry"),
    path("session/", views.session_page, name="session_page"),
    path("api/sessions/<str:session_id>/remaining",
         views.session_remaining, name="session_remaining"),
    path("api/sessions/<str:session_id>/last-snapshot",
         views.last_snapshot, name="last_snapshot"),
    # Step 9
    path("api/sessions/<str:session_id>/events",
         anticheat.post_event, name="anticheat_event"),
]
