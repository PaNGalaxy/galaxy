"""
Pingfed OpenID Connect backend for Galaxy.

This backend extends Galaxy's base OIDC implementation with PingFed-specific features.
"""

import jwt
from pkce import generate_pkce_pair

from galaxy.authnz.oidc import GalaxyOpenIdConnect

VERIFIER_COOKIE_NAME = "galaxy-oidc-verifier"


class PingfedOpenIdConnect(GalaxyOpenIdConnect):
    name = "pingfed"
    EXTRA_DATA = GalaxyOpenIdConnect.EXTRA_DATA + ["expires_in"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.trans = self.strategy.config.get("GALAXY_TRANS")

    def auth_params(self, state=None):
        """
        Add Galaxy-specific parameters to the authorization request.

        This method adds:
        - PKCE parameters (if enabled)
        """
        params = super().auth_params(state)

        # Add PKCE parameters if enabled
        if self.PKCE_ENABLED:
            # Generate PKCE challenge
            code_verifier, code_challenge = generate_pkce_pair(96)
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            # Store verifier in cookies
            self.trans.set_cookie(name=VERIFIER_COOKIE_NAME, value=code_verifier)

        return params

    def auth_complete_params(self, state=None):
        """
        Add PKCE code verifier to token request if PKCE is enabled.
        """
        params = super().auth_complete_params(state)

        # Add PKCE code verifier if it was used
        if self.PKCE_ENABLED:
            code_verifier = self.trans.get_cookie(name=VERIFIER_COOKIE_NAME)
            if code_verifier:
                params["code_verifier"] = code_verifier
                # Remove the cookie now that it is no longer necessary.
                try:
                    self.trans.set_cookie(name=VERIFIER_COOKIE_NAME, value="", age=-1)
                except Exception:
                    # Something went wrong, but we have little choice but to continue.
                    pass

        return params

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
