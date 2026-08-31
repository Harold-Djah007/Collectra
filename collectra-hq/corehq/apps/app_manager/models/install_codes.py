import secrets
from urllib.parse import urljoin

from django.db import IntegrityError, models, transaction
from django.urls import reverse

CODE_ALPHABET = 'abcdefghijkmnopqrstuvwxyz23456789'
CODE_LENGTH = 7
MAX_CODE_ATTEMPTS = 8


class AppInstallCode(models.Model):
    """Maps a short install code to an ODK profile URL when Bitly is unavailable."""

    domain = models.CharField(max_length=255)
    code = models.CharField(max_length=16, unique=True)
    target_url = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('domain', 'target_url')

    @classmethod
    def absolute_url_for(cls, domain, target_url, url_base):
        mapping = cls._get_or_create_mapping(domain, target_url)
        return urljoin(url_base, reverse('app_install_code', args=[mapping.code]))

    @classmethod
    def _get_or_create_mapping(cls, domain, target_url):
        existing = cls.objects.filter(domain=domain, target_url=target_url).first()
        if existing:
            return existing

        for _ in range(MAX_CODE_ATTEMPTS):
            mapping = cls(domain=domain, code=cls._generate_code(), target_url=target_url)
            try:
                with transaction.atomic():
                    mapping.save()
                return mapping
            except IntegrityError:
                existing = cls.objects.filter(domain=domain, target_url=target_url).first()
                if existing:
                    return existing
        raise RuntimeError('Unable to allocate a unique Collectra app install code')

    @staticmethod
    def _generate_code():
        return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
