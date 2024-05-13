try:
    from fs.sshfs import SSHFS
except ImportError:
    SSHFS = None
import logging
import re
from typing import (
    Optional,
    Union,
)

import jwt
from paramiko.transport import Transport

from . import (
    FilesSourceOptions,
    FilesSourceProperties,
)
from ._pyfilesystem2 import PyFilesystem2FilesSource

log = logging.getLogger(__name__)
MAX_LENGTH = 511


class OIDCTransport(Transport):
    def auth_password(self, username, password):
        self._token = password
        return self.auth_interactive(username, self.interaction_handler)

    def interaction_handler(self, _title, _instructions, prompt_list):
        resp = []
        token = self._token
        for pr in prompt_list:
            if pr[0].strip() == "Password:":
                if len(self._token) > MAX_LENGTH:
                    resp.append(self._token[0:MAX_LENGTH])
                    self._token = self._token[MAX_LENGTH:]
            elif pr[0].strip() == "Next:":
                if len(self._token) == 0:
                    resp.append("token_end")
                elif len(self._token) > MAX_LENGTH:
                    resp.append(self._token[0:MAX_LENGTH])
                    self._token = self._token[MAX_LENGTH:]
                else:
                    resp.append(token)
                    self._token = ""
        return tuple(resp)


class SshOidcFilesSource(PyFilesystem2FilesSource):
    plugin_type = "sshoidc"
    required_module = SSHFS
    required_package = "fs.sshfs"

    def _open_fs(self, user_context=None, opts: Optional[FilesSourceOptions] = None):
        props = self._serialization_props(user_context)
        extra_props: Union[FilesSourceProperties, dict] = opts.extra_props or {} if opts else {}
        path = props.pop("path")
        username_in_token = props.pop("username_in_token")
        username_template = props.pop("username_template")
        oidc_token = props.pop("oidc_token")
        props["passwd"] = oidc_token
        user = jwt.decode(oidc_token, options={"verify_signature": False})[username_in_token]
        match = re.match(username_template, user)
        props["user"] = match.group(0) if match else ""
        props["keepalive"] = 0
        props["transport_factory"] = OIDCTransport
        props["look_for_keys"] = False

        handle = SSHFS(**{**props, **extra_props})
        if path:
            handle = handle.opendir(path)
        return handle


__all__ = ("SshOidcFilesSource",)
