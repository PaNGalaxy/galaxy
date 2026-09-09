"""Azure OpenID Connect backend for Galaxy."""

import logging

from msal import ConfidentialClientApplication
from social_core.backends.azuread_tenant import AzureADV2TenantOAuth2
from social_core.exceptions import AuthTokenError

from galaxy.authnz.oidc_utils import set_id_token_expiration


class GalaxyAzureADV2TenantOAuth2(AzureADV2TenantOAuth2):
    name = "azuread-v2-tenant-oauth2"

    def extra_data(self, user, uid, response, details, pipeline_kwargs):
        data = super().extra_data(user, uid, response, details, pipeline_kwargs)
        set_id_token_expiration(data)
        return data

    def refresh_token(self, token, *args, **kwargs):
        logging.getLogger("msal").setLevel(logging.WARN)
        client_id, client_secret = self.get_key_and_secret()
        app = ConfidentialClientApplication(
            client_id,
            client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
        )
        response = app.acquire_token_by_refresh_token(
            token,
            scopes=["https://graph.microsoft.com/.default"],
        )
        if "error" in response:
            raise AuthTokenError(self, response.get("error_description", response["error"]))
        return response
