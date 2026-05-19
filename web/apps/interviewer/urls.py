from django.urls import path

from . import views

app_name = "interviewer"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/create", views.create_session, name="create_session"),
    path("dashboard/<str:session_id>/reentry", views.mint_reentry, name="mint_reentry"),
    path("dashboard/<str:session_id>/observe", views.observe, name="observe"),
    path("dashboard/<str:session_id>/review", views.review, name="review"),
]
