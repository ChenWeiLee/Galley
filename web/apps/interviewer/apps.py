from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InterviewerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "web.apps.interviewer"
    label = "interviewer"
    verbose_name = _("Interviewer")
