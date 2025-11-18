"""
ASGI config for Nova Ledger project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nova_ledger.settings')

application = get_asgi_application()
