"""API key retrieval through BaseAuth

Sample usage

.. code-block::

    curl --user zipzap@foo.com:password http://localhost:8080/api/authenticate/baseauth

Returns

.. code-block:: json

    {
        "api_key": "baa4d6e3a156d3033f05736255f195f9"
    }

"""
import time

import jwt
from fastapi import Request

from galaxy.managers.context import ProvidesAppContext
from galaxy.model.db.user import get_user_by_email
from galaxy.security.vault import UserVaultWrapper
from galaxy.schema.schema import ChatResponse, TokenExchangePayload, TokenExchangeResponse
from galaxy.web import expose_api_anonymous_and_sessionless
from galaxy.webapps.base.webapp import GalaxyWebTransaction
from galaxy.webapps.galaxy.api import DependsOnTrans
from galaxy.webapps.galaxy.services.authenticate import (
    APIKeyResponse,
    AuthenticationService,
)
from . import (
    BaseGalaxyAPIController,
    depends,
    Router,
)

router = Router(tags=["authenticate"])


class AuthenticationController(BaseGalaxyAPIController):
    authentication_service = depends(AuthenticationService)

    @expose_api_anonymous_and_sessionless
    def options(self, trans: GalaxyWebTransaction, **kwd):
        """
        A no-op endpoint to return generic OPTIONS for the API.
        Any OPTIONS request to /api/* maps here.
        Right now this is solely to inform preflight CORS checks, which are API wide.
        Might be better placed elsewhere, but for now this is the initial entrypoint for relevant consumers.
        """
        trans.response.headers["Access-Control-Allow-Headers"] = "*"
        trans.response.headers["Access-Control-Max-Age"] = 600
        # No need to set allow-methods for preflight cors check, I don't think.
        # When this is actually granular, endpoints should *probably* respond appropriately.
        # trans.response.headers['Access-Control-Allow-Methods'] = 'POST, PUT, GET, OPTIONS, DELETE'


@router.cbv
class FastAPIAuthenticate:
    authentication_service: AuthenticationService = depends(AuthenticationService)

    @router.get(
        "/api/authenticate/baseauth",
        summary="Returns returns an API key for authenticated user based on BaseAuth headers.",
    )
    def get_api_key(self, request: Request) -> APIKeyResponse:
        # TODO: use fastapi.security mechanism
        authorization = request.headers.get("Authorization")
        auth = {"HTTP_AUTHORIZATION": authorization}
        return self.authentication_service.get_api_key(auth, request)

@router.cbv
class FastAPITokenExchange:
    def get_globus_token(self, trans: ProvidesAppContext, user) -> tuple[str, float]:
        import globus_sdk
        from globus_sdk.exc import GlobusAPIError

        client_id = user.extra_preferences.get("globus|client_id")
        if not client_id:
            raise RuntimeError("Missing Globus client_id in user preferences.")

        user_vault = UserVaultWrapper(trans.app.vault, user)
        refresh_token = user_vault.read_secret("preferences/globus/refresh_token")
        if not refresh_token:
            raise RuntimeError("Missing Globus refresh token in user preferences.")

        client = globus_sdk.NativeAppAuthClient(client_id)
        try:
            token_response = client.oauth2_refresh_token(refresh_token)
        except GlobusAPIError as exc:
            raise RuntimeError(f"Globus token refresh failed with HTTP {exc.http_status}.") from exc


        access_token = token_response.get("access_token", None)
        if not access_token:
            raise RuntimeError("Refreshed Globus token response did not include an access token.")

        expires_at = token_response.get("expires_at_seconds")
        if expires_at is None:
            expires_in = token_response.get("expires_in")
            if expires_in is None:
                raise RuntimeError("Refreshed Globus token response did not include token expiration.")
            expires_at = time.time() + expires_in

        return access_token, float(expires_at)

    def _error_response(self, message: str) -> TokenExchangeResponse:
        return TokenExchangeResponse(response="", expires_at=None, error_code=1, error_message=message)

    @router.post("/api/authenticate/exchange")
    def query(
        self,
        payload: TokenExchangePayload,
        trans: ProvidesAppContext = DependsOnTrans,
        summary="Exchange OIDC token for another token/api key",
        description="Allows to exchange NDIP OIDC token for "
                    "another token, that is needed for some service (like IRI api, data transfer, etc.). "
                    "It is not meant to represent part of Galaxy's stable, user facing API",
        tags=["oidc_tokens"],
    ) -> TokenExchangeResponse:
        try:
            decoded_token = jwt.decode(
                payload.ndip_token,
                options={"verify_signature": False, "verify_aud": False, "verify_exp": False},
            )
        except Exception as exc:
            return self._error_response(f"Unable to decode NDIP token: {exc}")

        email = decoded_token.get("preferred_username", None) or decoded_token.get("email", None)
        if not email:
            return self._error_response("Token does not contain an email claim.")

        user = get_user_by_email(trans.sa_session, email)
        if user is None:
            return self._error_response(f"No Galaxy user found for email: {email}")

        if payload.exchange_to == "globus_iri":
            try:
                response, expires_at = self.get_globus_token(trans, user)
            except Exception as exc:
                return self._error_response(str(exc))
        elif payload.exchange_to == "globus_transfer":
            return self._error_response(f"NDIP token exchange to: {payload.exchange_to} is not implemented.")
        else:
            return self._error_response(f"NDIP token exchange to: {payload.exchange_to} is not implemented.")

#        job = self.__authorize_job_access(trans, job_id, job_key)
#        trans.app.authnz_manager.refresh_expiring_oidc_tokens(trans, job.user)  # type: ignore[attr-defined]
#        tokens = job.user.get_oidc_tokens(provider_name_to_backend(provider))
        return TokenExchangeResponse(response=response, expires_at=expires_at, error_code=0, error_message="")
