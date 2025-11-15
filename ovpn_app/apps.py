"""
Django app configuration for OpenVPN management
"""

from django.apps import AppConfig


class OvpnAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ovpn_app"
    verbose_name = "OpenVPN Management"

    def ready(self):
        # Import signals
        try:
            pass
        except ImportError:
            pass
