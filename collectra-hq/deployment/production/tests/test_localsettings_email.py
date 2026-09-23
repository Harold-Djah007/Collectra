"""Check production email settings without starting the HQ service stack."""

import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


SETTINGS_PATH = Path(__file__).resolve().parents[1] / "localsettings.py"
BASE_ENV = {
    "COLLECTRA_HOST": "collectra.example.com",
    "COLLECTRA_ADMIN_EMAIL": "admin@example.com",
    "DJANGO_SECRET_KEY": "test-secret",
    "POSTGRES_PASSWORD": "test-postgres-password",
    "COUCHDB_PASSWORD": "test-couch-password",
    "MINIO_ROOT_USER": "test-minio-user",
    "MINIO_ROOT_PASSWORD": "test-minio-password",
    "FORMPLAYER_AUTH_KEY": "test-formplayer-key",
}


class ProductionEmailSettingsTest(unittest.TestCase):
    def load_settings(self, **email_env):
        with patch.dict(os.environ, {**BASE_ENV, **email_env}, clear=True):
            return runpy.run_path(str(SETTINGS_PATH))

    def test_console_backend_remains_the_default(self):
        settings = self.load_settings()
        self.assertEqual(
            settings["EMAIL_BACKEND"],
            "django.core.mail.backends.console.EmailBackend",
        )
        self.assertEqual(settings["DEFAULT_FROM_EMAIL"], "admin@example.com")

    def test_smtp_uses_configured_sender(self):
        settings = self.load_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_SMTP_HOST="smtp.example.com",
            EMAIL_LOGIN="notifications@example.com",
            EMAIL_PASSWORD="test-password",
            COLLECTRA_FROM_EMAIL="Collectra <notifications@example.com>",
        )
        self.assertEqual(settings["EMAIL_SMTP_HOST"], "smtp.example.com")
        self.assertEqual(
            settings["DEFAULT_FROM_EMAIL"],
            "Collectra <notifications@example.com>",
        )
        self.assertEqual(settings["EMAIL_SUBJECT_PREFIX"], "[Collectra] ")

    def test_incomplete_smtp_configuration_fails_early(self):
        for missing in ("EMAIL_SMTP_HOST", "EMAIL_LOGIN", "EMAIL_PASSWORD"):
            credentials = {
                "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "EMAIL_SMTP_HOST": "smtp.example.com",
                "EMAIL_LOGIN": "notifications@example.com",
                "EMAIL_PASSWORD": "test-password",
            }
            credentials[missing] = ""
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(
                    RuntimeError, "SMTP email requires"
                ):
                    self.load_settings(**credentials)
