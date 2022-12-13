try:
    from fs.sshfs import SSHFS
except ImportError:
    SSHFS = None
from ._pyfilesystem2 import PyFilesystem2FilesSource
import logging
import jwt
import re
from paramiko.transport import Transport

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
                    resp.append('token_end')
                elif len(self._token) > MAX_LENGTH:
                    resp.append(self._token[0:MAX_LENGTH])
                    self._token = self._token[MAX_LENGTH:]
                else:
                    resp.append(token)
                    self._token = ''
        return tuple(resp)


class SshOidcFilesSource(PyFilesystem2FilesSource):
    plugin_type = "sshoidc"
    required_module = SSHFS
    required_package = "sshfs"

    def _open_fs(self, user_context):
        props = self._serialization_props(user_context)
        path = props.pop("path")
        username_in_token = props.pop("username_in_token")
        username_template = props.pop("username_template")
        oidc_token = props.pop("oidc_token")
        props['passwd'] = oidc_token
        user = jwt.decode(oidc_token, options={"verify_signature": False})[username_in_token]
        props['user'] = re.match(username_template, user).group(0)
        props['keepalive'] = 0
        props['transport_factory'] = OIDCTransport
        props['look_for_keys'] = False

        handle = SSHFS(**props)
        if path:
            handle = handle.opendir(path)
        return handle


__all__ = ("SshOidcFilesSource",)
