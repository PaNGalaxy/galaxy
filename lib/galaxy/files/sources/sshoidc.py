try:
    from .sshfs.sshfs import SSHFS
except ImportError:
    FS = None 

from ._pyfilesystem2 import PyFilesystem2FilesSource
import logging

log = logging.getLogger(__name__)

class SshOidcFilesSource(PyFilesystem2FilesSource):
    plugin_type = "sshoidc"
    required_module = SSHFS
    required_package = "sshfs"

    def _open_fs(self, user_context):
        props = self._serialization_props(user_context)
        path = props.pop("path")   
        props['id_token'] = user_context.trans.user.id_token
        props['user']  = user_context.trans.user.username
        handle = SSHFS(**props)
        if path:
            handle = handle.opendir(path)
        return handle

__all__ = ("SshOidcFilesSource",)
