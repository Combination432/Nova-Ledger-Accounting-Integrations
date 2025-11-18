"""
WSGI config for Nova Ledger project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nova_ledger.settings')

application = get_wsgi_application()
