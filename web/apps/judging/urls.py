from django.urls import path

from . import callback, submit_view, views

app_name = "judging"

urlpatterns = [
    # Walking skeleton (Step 3, kept per Patch #1 option a)
    path("skeleton/<slug:slug>", views.skeleton_page, name="skeleton_page"),
    path("skeleton/submit", views.skeleton_submit, name="skeleton_submit"),
    path("api/submissions/<str:sub_id>", views.submission_status, name="submission_status"),
    # Step 8: real submission flow
    path("api/sessions/<str:session_id>/submit", submit_view.submit, name="submit"),
    path("judge0/callback", callback.judge0_callback, name="judge0_callback"),
]
