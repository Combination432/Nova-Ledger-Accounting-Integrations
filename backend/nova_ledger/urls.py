"""
URL configuration for Nova Ledger project.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API endpoints
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/transactions/', include('apps.transactions.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/integrations/', include('apps.integrations.urls')),
    path('api/reporting/', include('apps.reporting.urls')),
    path('api/revenue/', include('apps.revenue_recognition.urls')),
]
