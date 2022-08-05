from ..objectstore import ConcreteObjectStore

import os
import requests

import logging

log = logging.getLogger(__name__)

from galaxy.util import (
    directory_hash_id,
    umask_fix_perms,
    unlink,
)
from galaxy.exceptions import (
    ObjectInvalid,
    ObjectNotFound,
)
from galaxy.util.path import safe_relpath

import shutil


def _config_xml_error(tag):
    msg = f"No {tag} element in config XML tree"
    raise Exception(msg)


def _config_dict_error(key):
    msg = "No {key} key in config dictionary".format(key=key)
    raise Exception(msg)


def parse_config_xml(config_xml):
    try:
        c_xml = config_xml.findall("cache")
        if not c_xml:
            _config_xml_error("cache")
        cache_size = float(c_xml[0].get("size", -1))
        staging_path = c_xml[0].get("path", None)


        rdb_xml = config_xml.findall("remote_data_broker_url")
        if not rdb_xml:
            _config_xml_error("remote_data_broker_url")
        rdb_url = rdb_xml[0].get("url", None)

        attrs = ("type", "path")
        e_xml = config_xml.findall("extra_dir")
        if not e_xml:
            _config_xml_error("extra_dir")
        extra_dirs = [{k: e.get(k) for k in attrs} for e in e_xml]

        return {
            "cache": {
                "size": cache_size,
                "path": staging_path,
            },
            "extra_dirs": extra_dirs,
            "remote_data_broker_url": rdb_url,
        }
    except Exception:
        # Toss it back up after logging, we can't continue loading at this point.
        log.exception("Malformed RDB ObjectStore Configuration XML -- unable to continue.")
        raise


class RdbBroker():
    def __init__(self, remote_broker_url):
        self.remote_broker_url = remote_broker_url

    def upload(self, key, source_path):
        token = "none"
        data = {"input_path": source_path, "token": token, "key": key}
        response = requests.post(self.remote_broker_url + "/upload", json=data)
        if response.status_code != 200:
            raise requests.HTTPError("wrong rdb response ", response.status_code, response.text)
    def download(self, key, dest_path):
        token = "none"
        data = {"key": key, "token": token, "output_path": dest_path}
        response = requests.post(self.remote_broker_url + "/download", json=data)
        if response.status_code != 200:
            return False
        return True

    def data_object_exists(self, key):
        token = "none"
        data = {"key": key, "token": token}
        response = requests.post(self.remote_broker_url + "/meta", json=data)
        if response.status_code != 200:
            return False
        res = response.json()
        if "exists" in res and res["exists"]==True:
            return True
        return False

    def get_size(self, key):
        token = "none"
        data = {"key": key, "token": token}
        response = requests.post(self.remote_broker_url + "/meta", json=data)
        if response.status_code != 200:
            return 0
        res = response.json()
        if not "size" in res:
            return 0
        return res["size"]

    def delete(self, key):
        pass


class RdbObjectStore(ConcreteObjectStore):
    """
    Object store implementation that uses ORNL remote data broker.

    This implementation should be considered beta and may be dropped from
    Galaxy at some future point or significantly modified.
    """
    store_type = "rdb"

    def to_dict(self):
        rval = super().to_dict()
        rval["remote_data_broker_url"] = self.remote_data_broker_url
        rval["cache"]=dict()
        rval["cache"]["size"] = self.cache_size
        rval["cache"]["path"] = self.staging_path
        return rval

    def __init__(self, config, config_dict):
        super().__init__(config, config_dict)
        self.remote_data_broker_url = config_dict.get("remote_data_broker_url", None)
        if self.remote_data_broker_url is None:
            _config_dict_error("remote_data_broker_url")

        self.rdb_broker = RdbBroker(self.remote_data_broker_url)
        cache_dict = config_dict["cache"]
        if cache_dict is None:
            _config_dict_error("cache")
        self.cache_size = cache_dict.get("size", -1)
        if self.cache_size is None:
            _config_dict_error("cache->size")
        self.staging_path = cache_dict.get("path") or self.config.object_store_cache_path
        if self.staging_path is None:
            _config_dict_error("cache->path")

        extra_dirs = {e["type"]: e["path"] for e in config_dict.get("extra_dirs", [])}
        if not extra_dirs:
            _config_dict_error("extra_dirs")
        self.extra_dirs.update(extra_dirs)

    def _in_cache(self, rel_path):
        """Check if the given dataset is in the local cache and return True if so."""
        cache_path = self._get_cache_path(rel_path)
        return os.path.exists(cache_path)

    def _construct_path(
            self,
            obj,
            base_dir=None,
            dir_only=None,
            extra_dir=None,
            extra_dir_at_root=False,
            alt_name=None,
            obj_dir=False,
            **kwargs,
    ):
        # extra_dir should never be constructed from provided data but just
        # make sure there are no shenanigans afoot
        if extra_dir and extra_dir != os.path.normpath(extra_dir):
            log.warning("extra_dir is not normalized: %s", extra_dir)
            raise ObjectInvalid("The requested object is invalid")
        # ensure that any parent directory references in alt_name would not
        # result in a path not contained in the directory path constructed here
        if alt_name:
            if not safe_relpath(alt_name):
                log.warning("alt_name would locate path outside dir: %s", alt_name)
                raise ObjectInvalid("The requested object is invalid")
            # alt_name can contain parent directory references, but S3 will not
            # follow them, so if they are valid we normalize them out
            alt_name = os.path.normpath(alt_name)
        rel_path = os.path.join(*directory_hash_id(self._get_object_id(obj)))
        if extra_dir is not None:
            if extra_dir_at_root:
                rel_path = os.path.join(extra_dir, rel_path)
            else:
                rel_path = os.path.join(rel_path, extra_dir)

        # for JOB_WORK directory
        if obj_dir:
            rel_path = os.path.join(rel_path, str(self._get_object_id(obj)))
        if base_dir:
            base = self.extra_dirs.get(base_dir)
            return os.path.join(base, rel_path)

        if not dir_only:
            rel_path = os.path.join(rel_path, alt_name if alt_name else f"dataset_{self._get_object_id(obj)}.dat")
        return rel_path

    def _get_cache_path(self, rel_path):
        return os.path.abspath(os.path.join(self.staging_path, rel_path))


    def _pull_into_cache(self, rel_path):
        log.debug("rdb _pull_into_cache")
        # Ensure the cache directory structure exists (e.g., dataset_#_files/)
        rel_path_dir = os.path.dirname(rel_path)
        if not os.path.exists(self._get_cache_path(rel_path_dir)):
            os.makedirs(self._get_cache_path(rel_path_dir), exist_ok=True)
        # Now pull in the file
        dest = self._get_cache_path(rel_path)
        file_ok = self.rdb_broker.download(rel_path,dest)
        self._fix_permissions(self._get_cache_path(rel_path_dir))
        return file_ok

    def _fix_permissions(self, rel_path):
        """Set permissions on rel_path"""
        for basedir, _, files in os.walk(rel_path):
            umask_fix_perms(basedir, self.config.umask, 0o777)
            for filename in files:
                path = os.path.join(basedir, filename)
                # Ignore symlinks
                if os.path.islink(path):
                    continue
                umask_fix_perms(path, self.config.umask, 0o666)


    # "interfaces to implement"

    def _exists(self, obj, **kwargs):
        log.debug("rdb _exists")
        rel_path = self._construct_path(obj, **kwargs)

        dir_only = kwargs.get("dir_only", False)
        base_dir = kwargs.get("base_dir", None)

        # Check cache and rdb
        if self._in_cache(rel_path) or (not dir_only and self.rdb_broker.data_object_exists(rel_path)):
            return True

        # dir_only does not get synced so shortcut the decision
        if dir_only and base_dir:
            # for JOB_WORK directory
            if not os.path.exists(rel_path):
                os.makedirs(rel_path, exist_ok=True)
            return True
        return False

    @classmethod
    def parse_xml(cls, config_xml):
        return parse_config_xml(config_xml)

    def file_ready(self, obj, **kwargs):
        log.debug("rdb file_ready")
        """
        A helper method that checks if a file corresponding to a dataset is
        ready and available to be used. Return ``True`` if so, ``False`` otherwise.
        """
        rel_path = self._construct_path(obj, **kwargs)
        # Make sure the size in cache is available in its entirety
        if self._in_cache(rel_path):
            if os.path.getsize(self._get_cache_path(rel_path)) == self.rdb_broker.get_size(rel_path):
                return True
        log.debug(
            "Waiting for dataset %s to transfer from OS: %s/%s",
            rel_path,
            os.path.getsize(self._get_cache_path(rel_path)),
            self.rdb_broker.get_size(rel_path),
        )
        return False

    def _create(self, obj, **kwargs):
        if not self._exists(obj, **kwargs):
            # Pull out locally used fields
            extra_dir = kwargs.get("extra_dir", None)
            extra_dir_at_root = kwargs.get("extra_dir_at_root", False)
            dir_only = kwargs.get("dir_only", False)
            alt_name = kwargs.get("alt_name", None)

            # Construct hashed path
            rel_path = os.path.join(*directory_hash_id(self._get_object_id(obj)))

            # Optionally append extra_dir
            if extra_dir is not None:
                if extra_dir_at_root:
                    rel_path = os.path.join(extra_dir, rel_path)
                else:
                    rel_path = os.path.join(rel_path, extra_dir)

            # Create given directory in cache
            cache_dir = os.path.join(self.staging_path, rel_path)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)

            if not dir_only:
                rel_path = os.path.join(rel_path, alt_name if alt_name else f"dataset_{self._get_object_id(obj)}.dat")
                open(os.path.join(self.staging_path, rel_path), "w").close()
                self.rdb_broker.upload(rel_path,self._get_cache_path(rel_path))
        log.debug("rdb _create")

    def _empty(self, obj, **kwargs):
        log.debug("rdb _empty")
        if self._exists(obj, **kwargs):
            return bool(self._size(obj, **kwargs) > 0)
        else:
            raise ObjectNotFound(f"objectstore.empty, object does not exist: {obj}, kwargs: {kwargs}")

    def _size(self, obj, **kwargs):
        log.debug("rdb _size")
        rel_path = self._construct_path(obj, **kwargs)
        if self._in_cache(rel_path):
            try:
                return os.path.getsize(self._get_cache_path(rel_path))
            except OSError as ex:
                log.info("Could not get size of file '%s' in local cache, will try iRODS. Error: %s", rel_path, ex)
        elif self._exists(obj, **kwargs):
            return self.rdb_broker.get_size(rel_path)
        log.warning("Did not find dataset '%s', returning 0 for size", rel_path)
        return 0

    def _delete(self, obj, entire_dir=False, **kwargs):
        log.debug("rdb _delete")
        rel_path = self._construct_path(obj, **kwargs)
        extra_dir = kwargs.get("extra_dir", None)
        base_dir = kwargs.get("base_dir", None)
        dir_only = kwargs.get("dir_only", False)
        obj_dir = kwargs.get("obj_dir", False)
        try:
            # Remove temporary data in JOB_WORK directory
            if base_dir and dir_only and obj_dir:
                shutil.rmtree(os.path.abspath(rel_path))
                return True

            # Delete from cache first
            if entire_dir and extra_dir:
                shutil.rmtree(self._get_cache_path(rel_path), ignore_errors=True)
            else:
                unlink(self._get_cache_path(rel_path), ignore_errors=True)

            # Delete from rdb as well
            if self.rdb_broker.data_object_exists(rel_path):
                self.rdb_broker.delete(rel_path)
                return True
        except OSError:
            log.exception("%s delete error", self._get_filename(obj, **kwargs))
        return False

    def _get_data(self, obj, **kwargs):
        log.debug("rdb _get_data")
        return "hello"

    def _get_filename(self, obj, **kwargs):
        log.debug("rdb _get_filename")
        base_dir = kwargs.get("base_dir", None)
        dir_only = kwargs.get("dir_only", False)
        obj_dir = kwargs.get("obj_dir", False)
        rel_path = self._construct_path(obj, **kwargs)

        # for JOB_WORK directory
        if base_dir and dir_only:
            return os.path.abspath(rel_path)

        cache_path = self._get_cache_path(rel_path)
        if (self._in_cache(rel_path) and dir_only):
            return cache_path
        elif (os.path.exists(self._get_cache_path(rel_path)) and
              os.path.getsize(self._get_cache_path(rel_path)) == self.rdb_broker.get_size(rel_path)):
            return cache_path
        # Check if the file exists in persistent storage and, if it does, pull it into cache
        elif self._exists(obj, **kwargs):
            if dir_only:  # Directories do not get pulled into cache
                return cache_path
            else:
                if self._pull_into_cache(rel_path):
                    return cache_path
        raise ObjectNotFound(f"objectstore.get_filename, no cache_path: {obj}, kwargs: {kwargs}")

    def _update_from_file(self, obj, file_name=None, create=False, **kwargs):
        log.debug("rdb _update_from_file")
        if create:
            self._create(obj, **kwargs)
        if self._exists(obj, **kwargs):
            rel_path = self._construct_path(obj, **kwargs)
            # Choose whether to use the dataset file itself or an alternate file
            if file_name:
                source_file = os.path.abspath(file_name)
                # Copy into cache
                cache_file = self._get_cache_path(rel_path)
                try:
                    if source_file != cache_file:
                        shutil.copy2(source_file, cache_file)
                    self._fix_permissions(cache_file)
                except OSError:
                    log.exception("Trouble copying source file '%s' to cache '%s'", source_file, cache_file)
            else:
                source_file = self._get_cache_path(rel_path)
            # Update the file on rdb
            self.rdb_broker.upload(rel_path, source_file)
        else:
            raise ObjectNotFound(f"objectstore.update_from_file, object does not exist: {obj}, kwargs: {kwargs}")

    def _get_store_usage_percent(self):
        log.debug("rdb _get_store_usage_percent, not implemented yet")
        return 0.0

    def _get_object_url(self, obj, extra_dir=None, extra_dir_at_root=False, alt_name=None):
        log.debug("rdb _get_object_url")
        return None

    def __build_kwargs(self, obj, **kwargs):
        kwargs["object_id"] = obj.id
        return kwargs

    def shutdown(self):
        pass
