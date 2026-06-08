"""
Pingfed OpenID Connect backend for Galaxy.

This backend extends Galaxy's base OIDC implementation with PingFed-specific features.
"""

import jwt

from galaxy.authnz.oidc import GalaxyOpenIdConnect


class PingfedOpenIdConnect(GalaxyOpenIdConnect):
    name = "pingfed"
    EXTRA_DATA = GalaxyOpenIdConnect.EXTRA_DATA + ["expires_in"]

    def extra_data(self, user, uid, response, details, pipeline_kwargs):
        data = super().extra_data(user, uid, response, details, pipeline_kwargs)
        id_token = data.get("id_token")
        if id_token and not data.get("expires") and not data.get("expires_in"):
            decoded_token = jwt.decode(id_token, options={"verify_signature": False})
            auth_time = decoded_token.get("auth_time") or decoded_token.get("iat")
            expires_at = decoded_token.get("exp")
            if auth_time is not None and expires_at is not None:
                data["expires_in"] = int(expires_at) - int(auth_time)
        return data

    def oidc_endpoint(self):
        """
        Return the OIDC endpoint for configuration discovery.

        PingFed typically uses URLs like:
        https://pingfed.example.com

        This allows administrators to configure the full PingFed issuer URL.
        """
        # Check if custom URL is configured
        if base_url := self.setting("URL"):
            # Remove potential trailing slash
            return base_url.rstrip("/")
        # Fall back to default OIDC endpoint discovery
        return super().oidc_endpoint()
