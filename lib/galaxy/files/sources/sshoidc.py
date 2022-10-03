try:
    from .sshfs.sshfs import SSHFS
except ImportError:
    FS = None
from ._pyfilesystem2 import PyFilesystem2FilesSource
import logging
import jwt
import re

log = logging.getLogger(__name__)

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
        props['id_token'] = oidc_token
        user = jwt.decode(props['id_token'], options={"verify_signature": False})[username_in_token]
        props['user'] = re.match(username_template, user).group(0)
        props ['keepalive'] = 0
        handle = SSHFS(**props)
        if path:
            handle = handle.opendir(path)
        return handle

__all__ = ("SshOidcFilesSource",)
