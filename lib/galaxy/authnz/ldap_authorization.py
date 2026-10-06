import logging

from galaxy.auth.providers.ldap_ad import LDAP
from galaxy.exceptions import AuthenticationFailed
from galaxy.util import string_as_bool

log = logging.getLogger(__name__)

DEFAULT_DENIAL_MESSAGE = (
    "Your account is not authorized for this Galaxy instance. Contact an administrator to request access."
)


def authorize(strategy, details, **kwargs):
    config = strategy.config.get("LDAP_AUTHORIZATION")
    if config is None:
        return
    if strategy.config["provider"] == "azure":
        details = {**details, "username": (details.get("email") or "").split("@", 1)[0]}
    trans = strategy.config["GALAXY_TRANS"]
    try:
        authenticator = next(
            auth for auth in trans.app.auth_manager.authenticators if auth.name == config["authenticator"]
        )
        if not isinstance(authenticator.plugin, LDAP):
            raise ValueError("LDAP authorization requires an LDAP authenticator")
        options = dict(authenticator.options, no_password_check=True, redact_username_in_logs=True)
        if "search-memberof-filter" in options and not (options["search-memberof-filter"] or "").strip():
            raise ValueError("search-memberof-filter must not be empty")
        if not options.get("search-fields"):
            raise ValueError("LDAP authorization requires search-fields for the directory lookup")
        identity_field = "username" if string_as_bool(options.get("login-use-username", False)) else "email"
        if not details.get(identity_field):
            raise ValueError("LDAP authorization identity is missing")
        from ldap.filter import escape_filter_chars

        result = type(authenticator.plugin)().authenticate(
            email=escape_filter_chars(details.get("email") or ""),
            username=escape_filter_chars(details.get("username") or ""),
            password=None,
            options=options,
            request=trans.request,
        )
        if result[0] is True:
            log.debug(
                "LDAP authorization approved login for provider %r, identity %r",
                strategy.config["provider"],
                details.get(identity_field),
            )
            return
    except Exception as error:
        log.warning("LDAP authorization lookup failed (%s)", type(error).__name__)
    log.warning("LDAP authorization rejected login for provider %r", strategy.config["provider"])
    raise AuthenticationFailed(config.get("denial_message") or DEFAULT_DENIAL_MESSAGE)
