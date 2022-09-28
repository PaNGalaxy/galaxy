try:
    from .sshfs import SSHFS
except ImportError:
    FS = None 

from ._pyfilesystem2 import PyFilesystem2FilesSource
import logging

log = logging.getLogger(__name__)

class SshOidcFilesSource(PyFilesystem2FilesSource):
    plugin_type = "sshoidc"
    required_module = FS
    required_package = "fs"

    def _open_fs(self, user_context):
        props = self._serialization_props(user_context)
        path = props.pop("path")   
        props['id_token'] = user_context.trans.user.id_token
        handle = SSHFS(**props)
        if path:
            handle = handle.opendir(path)
        return handle

__all__ = ("SshOidcFilesSource",)
