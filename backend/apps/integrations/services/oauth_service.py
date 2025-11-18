"""
OAuth 2.0 service for managing platform integrations.
Handles authorization flows, token management, and refresh for all platforms.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
import requests
import logging
import secrets

from ..models import Integration

logger = logging.getLogger(__name__)


class OAuthService:
    """
    Centralized OAuth service for all platform integrations.
    Supports authorization code flow with PKCE where applicable.
    """

    # Platform-specific OAuth configurations
    PLATFORM_CONFIG = {
        'shopify': {
            'authorize_url': 'https://{shop}.myshopify.com/admin/oauth/authorize',
            'token_url': 'https://{shop}.myshopify.com/admin/oauth/access_token',
            'scopes': [
                'read_orders', 'read_products', 'read_customers',
                'read_fulfillments', 'read_inventory', 'read_locations',
                'read_price_rules', 'read_discounts', 'read_shipping'
            ],
            'client_id_setting': 'SHOPIFY_CLIENT_ID',
            'client_secret_setting': 'SHOPIFY_CLIENT_SECRET',
        },
        'stripe': {
            'authorize_url': 'https://connect.stripe.com/oauth/authorize',
            'token_url': 'https://connect.stripe.com/oauth/token',
            'scopes': ['read_write'],
            'client_id_setting': 'STRIPE_CLIENT_ID',
            'client_secret_setting': 'STRIPE_CLIENT_SECRET',
        },
        'quickbooks': {
            'authorize_url': 'https://appcenter.intuit.com/connect/oauth2',
            'token_url': 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer',
            'revoke_url': 'https://developer.api.intuit.com/v2/oauth2/tokens/revoke',
            'scopes': ['com.intuit.quickbooks.accounting'],
            'client_id_setting': 'QUICKBOOKS_CLIENT_ID',
            'client_secret_setting': 'QUICKBOOKS_CLIENT_SECRET',
            'uses_pkce': True,  # QuickBooks recommends PKCE
        },
    }

    def __init__(self, platform: str, organization=None):
        """
        Initialize OAuth service for a specific platform.

        Args:
            platform: Platform name (shopify, stripe, quickbooks)
            organization: Organization object for scoping
        """
        self.platform = platform.lower()
        self.organization = organization

        if self.platform not in self.PLATFORM_CONFIG:
            raise ValueError(f"Unsupported platform: {platform}")

        self.config = self.PLATFORM_CONFIG[self.platform]
        self.client_id = getattr(settings, self.config['client_id_setting'], None)
        self.client_secret = getattr(settings, self.config['client_secret_setting'], None)

        if not self.client_id or not self.client_secret:
            logger.warning(
                f"Missing OAuth credentials for {platform}. "
                f"Set {self.config['client_id_setting']} and {self.config['client_secret_setting']} in settings."
            )

    def generate_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        shop: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, str, Optional[str]]:
        """
        Generate OAuth authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: CSRF protection state token (generated if not provided)
            shop: Shopify shop name (required for Shopify)
            **kwargs: Additional platform-specific parameters

        Returns:
            Tuple of (authorization_url, state, code_verifier)
            code_verifier is only returned for PKCE flows
        """
        if not state:
            state = secrets.token_urlsafe(32)

        # Base parameters
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'scope': ' '.join(self.config['scopes']),
        }

        code_verifier = None

        # Platform-specific handling
        if self.platform == 'shopify':
            if not shop:
                raise ValueError("Shopify OAuth requires 'shop' parameter")

            authorize_url = self.config['authorize_url'].format(shop=shop)
            # Shopify uses different parameter names
            params = {
                'client_id': self.client_id,
                'scope': ','.join(self.config['scopes']),  # Comma-separated for Shopify
                'redirect_uri': redirect_uri,
                'state': state,
            }

        elif self.platform == 'stripe':
            authorize_url = self.config['authorize_url']
            params['response_type'] = 'code'
            # Stripe-specific parameters
            if 'stripe_user' in kwargs:
                params['stripe_user'] = kwargs['stripe_user']

        elif self.platform == 'quickbooks':
            authorize_url = self.config['authorize_url']
            params['response_type'] = 'code'

            # PKCE for QuickBooks
            if self.config.get('uses_pkce'):
                code_verifier = secrets.token_urlsafe(64)
                # For simplicity, using plain code challenge
                # In production, use SHA256 hashing
                params['code_challenge'] = code_verifier
                params['code_challenge_method'] = 'plain'

        else:
            authorize_url = self.config['authorize_url']
            params['response_type'] = 'code'

        # Build URL
        url_params = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{authorize_url}?{url_params}"

        logger.info(f"Generated {self.platform} OAuth URL for organization {self.organization}")

        return full_url, state, code_verifier

    def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
        shop: Optional[str] = None,
        code_verifier: Optional[str] = None,
        realm_id: Optional[str] = None
    ) -> Dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: Same redirect URI used in authorization
            shop: Shopify shop name (required for Shopify)
            code_verifier: PKCE code verifier (for QuickBooks)
            realm_id: QuickBooks company/realm ID

        Returns:
            Dict with token information
        """
        # Build token request
        if self.platform == 'shopify':
            if not shop:
                raise ValueError("Shopify token exchange requires 'shop' parameter")

            token_url = self.config['token_url'].format(shop=shop)
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
            }

        elif self.platform == 'stripe':
            token_url = self.config['token_url']
            data = {
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
            }

        elif self.platform == 'quickbooks':
            token_url = self.config['token_url']
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
            }

            if code_verifier:
                data['code_verifier'] = code_verifier

            # QuickBooks uses Basic Auth
            auth = (self.client_id, self.client_secret)

        else:
            token_url = self.config['token_url']
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
            }

        # Make token request
        try:
            headers = {'Accept': 'application/json'}

            if self.platform == 'quickbooks':
                response = requests.post(
                    token_url,
                    data=data,
                    headers=headers,
                    auth=auth,
                    timeout=10
                )
            else:
                response = requests.post(
                    token_url,
                    data=data,
                    headers=headers,
                    timeout=10
                )

            response.raise_for_status()
            token_data = response.json()

            # Normalize response across platforms
            normalized = {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_in': token_data.get('expires_in'),
                'scope': token_data.get('scope'),
                'raw_response': token_data,
            }

            # Platform-specific fields
            if self.platform == 'shopify':
                normalized['shop'] = shop
            elif self.platform == 'stripe':
                normalized['stripe_user_id'] = token_data.get('stripe_user_id')
                normalized['stripe_publishable_key'] = token_data.get('stripe_publishable_key')
            elif self.platform == 'quickbooks':
                normalized['realm_id'] = realm_id
                normalized['x_refresh_token_expires_in'] = token_data.get('x_refresh_token_expires_in')

            logger.info(f"Successfully exchanged code for {self.platform} token")

            return normalized

        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for {self.platform} token: {str(e)}")
            raise

    def refresh_access_token(self, integration: Integration) -> Dict:
        """
        Refresh an expired access token.

        Args:
            integration: Integration object with refresh token

        Returns:
            Dict with new token information
        """
        if not integration.oauth_refresh_token:
            raise ValueError("No refresh token available")

        # Build refresh request
        if self.platform == 'shopify':
            # Shopify doesn't use refresh tokens - tokens don't expire
            logger.warning("Shopify tokens don't expire - refresh not needed")
            return {
                'access_token': integration.oauth_access_token,
                'expires_in': None,
            }

        elif self.platform == 'stripe':
            # Stripe tokens don't expire by default
            logger.info("Stripe tokens don't expire - refresh not needed")
            return {
                'access_token': integration.oauth_access_token,
                'expires_in': None,
            }

        elif self.platform == 'quickbooks':
            token_url = self.config['token_url']
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': integration.oauth_refresh_token,
            }
            auth = (self.client_id, self.client_secret)

        else:
            token_url = self.config['token_url']
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': integration.oauth_refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }

        try:
            headers = {'Accept': 'application/json'}

            if self.platform == 'quickbooks':
                response = requests.post(
                    token_url,
                    data=data,
                    headers=headers,
                    auth=auth,
                    timeout=10
                )
            else:
                response = requests.post(
                    token_url,
                    data=data,
                    headers=headers,
                    timeout=10
                )

            response.raise_for_status()
            token_data = response.json()

            # Update integration
            integration.oauth_access_token = token_data['access_token']

            if 'refresh_token' in token_data:
                integration.oauth_refresh_token = token_data['refresh_token']

            if 'expires_in' in token_data:
                integration.oauth_token_expiry = timezone.now() + timedelta(seconds=token_data['expires_in'])

            integration.save(update_fields=['oauth_access_token', 'oauth_refresh_token', 'oauth_token_expiry'])

            logger.info(f"Successfully refreshed {self.platform} token for integration {integration.id}")

            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in'),
                'raw_response': token_data,
            }

        except requests.RequestException as e:
            logger.error(f"Failed to refresh {self.platform} token: {str(e)}")
            raise

    def revoke_token(self, integration: Integration) -> bool:
        """
        Revoke an access token.

        Args:
            integration: Integration object

        Returns:
            True if successful
        """
        if not integration.oauth_access_token:
            logger.warning("No access token to revoke")
            return True

        # Only QuickBooks has a revoke endpoint
        if self.platform == 'quickbooks':
            try:
                revoke_url = self.config['revoke_url']
                data = {
                    'token': integration.oauth_refresh_token or integration.oauth_access_token,
                }
                auth = (self.client_id, self.client_secret)

                response = requests.post(
                    revoke_url,
                    data=data,
                    auth=auth,
                    timeout=10
                )

                response.raise_for_status()

                logger.info(f"Revoked {self.platform} token for integration {integration.id}")

            except requests.RequestException as e:
                logger.error(f"Failed to revoke {self.platform} token: {str(e)}")
                return False

        # Clear tokens from database
        integration.oauth_access_token = ''
        integration.oauth_refresh_token = ''
        integration.oauth_token_expiry = None
        integration.is_active = False
        integration.connection_status = 'disconnected'
        integration.save(
            update_fields=['oauth_access_token', 'oauth_refresh_token',
                          'oauth_token_expiry', 'is_active', 'connection_status']
        )

        return True

    def is_token_expired(self, integration: Integration) -> bool:
        """
        Check if access token is expired.

        Args:
            integration: Integration object

        Returns:
            True if token is expired or expiring soon (within 5 minutes)
        """
        if not integration.oauth_token_expiry:
            return False  # No expiry set (Shopify, Stripe)

        # Consider expired if expiring within 5 minutes
        buffer = timedelta(minutes=5)
        return timezone.now() >= (integration.oauth_token_expiry - buffer)

    def get_valid_token(self, integration: Integration) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Args:
            integration: Integration object

        Returns:
            Valid access token
        """
        if self.is_token_expired(integration):
            logger.info(f"Token expired for integration {integration.id}, refreshing...")
            token_data = self.refresh_access_token(integration)
            return token_data['access_token']

        return integration.oauth_access_token
