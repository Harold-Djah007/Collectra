"""Validate Redis URL handling without connecting to production services."""

import unittest

import test_localsettings_email


class ProductionRedisSettingsTest(unittest.TestCase):
    def load_settings(self, **env):
        return test_localsettings_email.ProductionEmailSettingsTest().load_settings(**env)

    def test_default_databases(self):
        settings = self.load_settings()
        self.assertEqual(settings["CACHES"]["default"]["LOCATION"], "redis://redis:6379/0")
        self.assertEqual(settings["CELERY_BROKER_URL"], "redis://redis:6379/1")
        self.assertEqual(settings["CACHES"]["default"]["TEST_LOCATION"], "redis://redis:6379/2")

    def test_existing_database_and_trailing_slash(self):
        for suffix in ("", "/", "/0", "/7"):
            with self.subTest(suffix=suffix):
                settings = self.load_settings(REDIS_URL=f"redis://redis:6379{suffix}")
                self.assertEqual(settings["CELERY_BROKER_URL"], "redis://redis:6379/1")

    def test_tls_credentials_and_query_are_preserved(self):
        settings = self.load_settings(REDIS_URL="rediss://user:password@redis:6380/7?socket_timeout=5")
        self.assertEqual(
            settings["CELERY_BROKER_URL"],
            "rediss://user:password@redis:6380/1?socket_timeout=5",
        )

    def test_invalid_endpoint_fails_early(self):
        for value in ("redis", "https://redis:6379", "redis:///0"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "REDIS_URL must"):
                    self.load_settings(REDIS_URL=value)

    def test_connection_options_reach_django_redis(self):
        settings = self.load_settings()
        self.assertEqual(
            settings["CACHES"]["default"]["OPTIONS"]["REDIS_CLIENT_KWARGS"],
            {"health_check_interval": 15},
        )
