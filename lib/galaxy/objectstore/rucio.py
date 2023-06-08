import copy
import time

try:
    from ..authnz.util import provider_name_to_backend
except ImportError:
    provider_name_to_backend = None
    pass
from ..objectstore import ConcreteObjectStore

import os

import logging

from galaxy.util import (
    directory_hash_id,
    umask_fix_perms,
    unlink, string_as_bool,
)
from galaxy.exceptions import (
    ObjectInvalid,
    ObjectNotFound,
)
from galaxy.util.path import safe_relpath

from rucio.client.downloadclient import DownloadClient
from rucio.common import utils
from rucio.client import Client
from rucio.client.uploadclient import UploadClient
from rucio.common.exception import (RSEWriteBlocked, NoFilesUploaded, NotAllFilesUploaded,
                                    RSENotFound, RSEProtocolNotSupported, InputValidationError)  # type: ignore
from rucio.common.utils import (generate_uuid)
from rucio.rse import rsemanager as rsemgr
import rucio.common

import shutil


log = logging.getLogger(__name__)


class InPlaceIngestClient(UploadClient):
    def ingest(self, items, summary_file_path=None, traces_copy_out=None, ignore_availability=False, activity=None):
        """
        :param items: List of dictionaries. Each dictionary describing a file to upload. Keys:
            path                  - path of the file that will be uploaded
            rse                   - rse expression/name (e.g. 'CERN-PROD_DATADISK') where to upload the file
            did_scope             - Optional: custom did scope (Default: user.<account>)
            did_name              - Optional: custom did name (Default: name of the file)
            dataset_scope         - Optional: custom dataset scope
            dataset_name          - Optional: custom dataset name
            dataset_meta          - Optional: custom metadata for dataset
            impl                  - Optional: name of the protocol implementation to be used to upload this item.
            force_scheme          - Optional: force a specific scheme (if PFN upload this will be overwritten) (Default: None)
            pfn                   - Optional: use a given PFN (this sets no_register to True, and no_register becomes mandatory)
            no_register           - Optional: if True, the file will not be registered in the rucio catalogue
            register_after_upload - Optional: if True, the file will be registered after successful upload
            lifetime              - Optional: the lifetime of the file after it was uploaded
            transfer_timeout      - Optional: time after the upload will be aborted
            guid                  - Optional: guid of the file
            recursive             - Optional: if set, parses the folder structure recursively into collections
        :param summary_file_path: Optional: a path where a summary in form of a json file will be stored
        :param traces_copy_out: reference to an external list, where the traces should be uploaded
        :param ignore_availability: ignore the availability of a RSE
        :param activity: the activity set to the rule if no dataset is specified

        :returns: 0 on success

        :raises InputValidationError: if any input arguments are in a wrong format
        :raises RSEWriteBlocked: if a given RSE is not available for writing
        :raises NoFilesUploaded: if no files were successfully uploaded
        :raises NotAllFilesUploaded: if not all files were successfully uploaded
        """
        # helper to get rse from rse_expression:

        logger = self.logger
        self.trace['uuid'] = generate_uuid()

        # check given sources, resolve dirs into files, and collect meta infos
        files = self._collect_and_validate_file_info(items)
        logger(logging.DEBUG, 'Num. of files that upload client is processing: {}'.format(len(files)))

        # check if RSE of every file is available for writing
        # and cache rse settings
        registered_dataset_dids = set()
        registered_file_dids = set()
        rse_expression = None
        for file in files:
            rse = file['rse']
            if not self.rses.get(rse):
                rse_settings = self.rses.setdefault(rse, rsemgr.get_rse_info(rse, vo=self.client.vo))
                if not ignore_availability and rse_settings['availability_write'] != 1:
                    raise RSEWriteBlocked('%s is not available for writing. No actions have been taken' % rse)

            dataset_scope = file.get('dataset_scope')
            dataset_name = file.get('dataset_name')
            file['rse'] = rse
            if dataset_scope and dataset_name:
                dataset_did_str = ('%s:%s' % (dataset_scope, dataset_name))
                file['dataset_did_str'] = dataset_did_str
                registered_dataset_dids.add(dataset_did_str)

            registered_file_dids.add('%s:%s' % (file['did_scope'], file['did_name']))
        wrong_dids = registered_file_dids.intersection(registered_dataset_dids)
        if len(wrong_dids):
            raise InputValidationError('DIDs used to address both files and datasets: %s' % str(wrong_dids))
        logger(logging.DEBUG, 'Input validation done.')

        # clear this set again to ensure that we only try to register datasets once
        registered_dataset_dids = set()
        num_succeeded = 0
        summary = []
        for file in files:
            basename = file['basename']
            logger(logging.INFO, 'Preparing upload for file %s' % basename)

            pfn = file.get('pfn')
            force_scheme = file.get('force_scheme')
            impl = file.get('impl')

            trace = copy.deepcopy(self.trace)
            # appending trace to list reference, if the reference exists
            if traces_copy_out is not None:
                traces_copy_out.append(trace)

            rse = file['rse']
            trace['scope'] = file['did_scope']
            trace['datasetScope'] = file.get('dataset_scope', '')
            trace['dataset'] = file.get('dataset_name', '')
            trace['remoteSite'] = rse
            trace['filesize'] = file['bytes']

            file_did = {'scope': file['did_scope'], 'name': file['did_name']}
            dataset_did_str = file.get('dataset_did_str')
            rse_settings = self.rses[rse]
            is_deterministic = rse_settings.get('deterministic', True)
            if not is_deterministic and not pfn:
                logger(logging.ERROR, 'PFN has to be defined for NON-DETERMINISTIC RSE.')
                continue
            if pfn and is_deterministic:
                logger(logging.WARNING,
                       'Upload with given pfn implies that no_register is True, except non-deterministic RSEs')
                no_register = True

            self._register_file(file, registered_dataset_dids, ignore_availability=ignore_availability,
                                activity=activity)

            file['upload_result'] = {0: True, 1: None, 'success': True, 'pfn': pfn}  # needs to be removed
            num_succeeded += 1
            trace['transferStart'] = time.time()
            trace['transferEnd'] = time.time()
            trace['clientState'] = 'DONE'
            file['state'] = 'A'
            logger(logging.INFO, 'Successfully uploaded file %s' % basename)
            self._send_trace(trace)

            if summary_file_path:
                summary.append(copy.deepcopy(file))

            replica_for_api = self._convert_file_for_api(file)
            try:
                self.client.update_replicas_states(rse, files=[replica_for_api])
            except Exception as error:
                logger(logging.ERROR, 'Failed to update replica state for file {}'.format(basename))
                logger(logging.DEBUG, 'Details: {}'.format(str(error)))

            # add file to dataset if needed
            if dataset_did_str and not no_register:
                try:
                    self.client.attach_dids(file['dataset_scope'], file['dataset_name'], [file_did])
                except Exception as error:
                    logger(logging.WARNING, 'Failed to attach file to the dataset')
                    logger(logging.DEBUG, 'Attaching to dataset {}'.format(str(error)))

        if num_succeeded == 0:
            raise NoFilesUploaded()
        elif num_succeeded != len(files):
            raise NotAllFilesUploaded()
        return 0


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

        attrs = ("type", "path")
        e_xml = config_xml.findall("extra_dir")
        if not e_xml:
            _config_xml_error("extra_dir")
        extra_dirs = [{k: e.get(k) for k in attrs} for e in e_xml]

        attrs = ("rse", "scheme", "ignore_checksum")
        e_xml = config_xml.findall("rucio_download_scheme")
        rucio_download_schemes = []
        if e_xml:
            rucio_download_schemes = [{k: e.get(k) for k in attrs} for e in e_xml]



        oidc_provider = config_xml.findtext("oidc_provider", None)

        e_xml = config_xml.findall("rucio")
        if e_xml:
            rucio_write_rse_name = e_xml[0].get("write_rse_name", None)
            rucio_write_rse_scheme = e_xml[0].get("write_rse_scheme", None)
            rucio_scope = e_xml[0].get("scope", None)
            rucio_register_only = string_as_bool(e_xml[0].get("register_only", "False"))
        else:
            rucio_write_rse_name = None
            rucio_write_rse_scheme = None
            rucio_scope = None
            rucio_register_only = False
            oidc_provider = None
        return {
            "cache": {
                "size": cache_size,
                "path": staging_path,
            },
            "extra_dirs": extra_dirs,
            "rucio_write_rse_name": rucio_write_rse_name,
            "rucio_write_rse_scheme": rucio_write_rse_scheme,
            "rucio_scope": rucio_scope,
            "rucio_register_only": rucio_register_only,
            "rucio_download_schemes": rucio_download_schemes,
            "oidc_provider": oidc_provider,
        }
    except Exception:
        # Toss it back up after logging, we can't continue loading at this point.
        log.exception("Malformed Rucio ObjectStore Configuration XML -- unable to continue.")
        raise


class RucioBroker():
    def __init__(self, rucio_config):
        self.write_rse_name = rucio_config["rucio_write_rse_name"]
        self.write_rse_scheme = rucio_config["rucio_write_rse_scheme"]
        self.scope = rucio_config["rucio_scope"]
        self.register_only = rucio_config["rucio_register_only"]
        self.download_schemes = rucio_config["rucio_download_schemes"]
        rucio.common.utils.PREFERRED_CHECKSUM = "md5"
        # rucio config is in a system rucio.cfg file

    def get_rucio_client(self):
        client = Client()
        return client

    def get_rucio_upload_client(self, auth_token=None):
        client = self.get_rucio_client()
        uc = UploadClient(_client=client)
        uc.auth_token = auth_token
        return uc

    def get_rucio_download_client(self, auth_token=None):
        client = self.get_rucio_client()
        dc = DownloadClient(client=client)
        dc.auth_token = auth_token
        return dc

    def get_rucio_ingest_client(self, auth_token=None):
        client = self.get_rucio_client()
        ic = InPlaceIngestClient(_client=client)
        ic.auth_token = auth_token
        return ic

    def register(self, key, source_path):
        key = os.path.basename(key)
        item = {
            "path": source_path,
            "rse": self.write_rse_name,
            "did_scope": self.scope,
            "did_name": key,
            "pfn": f"file://localhost/{source_path}",
        }
        items = [item]
        self.get_rucio_ingest_client().ingest(items)

    def upload(self, key, source_path):
        key = os.path.basename(key)
        item = {
            "path": source_path,
            "rse": self.write_rse_name,
            "did_scope": self.scope,
            "did_name": key,
            "force_scheme": self.write_rse_scheme,
        }
        items = [item]
        self.get_rucio_upload_client().upload(items)

    def download(self, key, dest_path, auth_token):
        key = os.path.basename(key)
        base_dir = os.path.dirname(dest_path)
        dids = [{"scope": self.scope, "name": key}]
        try:
            repl = next(self.get_rucio_client().list_replicas(dids))["rses"].keys()
            item = None
            for rse_scheme in self.download_schemes:
                if rse_scheme['rse'] in repl:
                    item = {
                        "did": f"{self.scope}:{key}",
                        "force_scheme": rse_scheme['scheme'],
                        "rse": rse_scheme['rse'],
                        "base_dir": base_dir,
                        "ignore_checksum": string_as_bool(rse_scheme['ignore_checksum']),
                        "no_subdir": True,
                    }
                    break
            if item is None:
                item = {
                    "did": f"{self.scope}:{key}",
                    "base_dir": base_dir,
                    "no_subdir": True,
                }
            items = [item]
            download_client = self.get_rucio_download_client(auth_token=auth_token)
            download_client.download_dids(items)
        except Exception as e:
            log.exception("Cannot download file:" + str(e))
            return False
        return True

    def data_object_exists(self, key):
        key = os.path.basename(key)
        dids = [{"scope": self.scope, "name": key}]
        try:
            repl = next(self.get_rucio_client().list_replicas(dids))
            return "AVAILABLE" in repl['states'].values()
        except:
            return False

    def get_size(self, key):
        key = os.path.basename(key)
        dids = [{"scope": self.scope, "name": key}]
        try:
            repl = next(self.get_rucio_client().list_replicas(dids))
            return repl['bytes']
        except:
            return 0

    def delete(self, key):
        rucio_client = self.get_rucio_client()
        key = os.path.basename(key)
        dids = [{"scope": self.scope, "name": key}]
        rses = next(rucio_client.list_replicas(dids))["rses"].keys()
        for rse in rses:
            rucio_client.delete_replicas(rse, dids)


class RucioObjectStore(ConcreteObjectStore):
    """
    Object store implementation that uses ORNL remote data broker.

    This implementation should be considered beta and may be dropped from
    Galaxy at some future point or significantly modified.
    """
    store_type = "rucio"

    def to_dict(self):
        rval = super().to_dict()
        rval.update(self.rucio_config)
        rval["cache"] = dict()
        rval["cache"]["size"] = self.cache_size
        rval["cache"]["path"] = self.staging_path
        return rval

    def __init__(self, config, config_dict):
        super().__init__(config, config_dict)
        self.rucio_config = {}
        self.rucio_config["rucio_write_rse_name"] = config_dict.get("rucio_write_rse_name", None)
        self.rucio_config["rucio_write_rse_scheme"] = config_dict.get("rucio_write_rse_scheme", None)
        self.rucio_config["rucio_register_only"] = config_dict.get("rucio_register_only", False)
        self.rucio_config["rucio_scope"] = config_dict.get("rucio_scope", None)
        self.rucio_config["rucio_download_schemes"] = config_dict.get("rucio_download_schemes", [])

        if 'RUCIO_WRITE_RSE_NAME' in os.environ:
            self.rucio_config["rucio_write_rse_name"] = os.environ['RUCIO_WRITE_RSE_NAME']
        if 'RUCIO_WRITE_RSE_SCHEME' in os.environ:
            self.rucio_config["rucio_write_rse_scheme"] = os.environ['RUCIO_WRITE_RSE_SCHEME']
        if 'RUCIO_REGISTER_ONLY' in os.environ:
            self.rucio_config["rucio_register_only"] = string_as_bool(os.environ['RUCIO_REGISTER_ONLY'])
        self.oidc_provider = config_dict.get("oidc_provider", None)
        self.rucio_broker = RucioBroker(self.rucio_config)
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

    def _pull_into_cache(self, rel_path, auth_token):
        log.debug("rucio _pull_into_cache: " + rel_path)
        # Ensure the cache directory structure exists (e.g., dataset_#_files/)
        rel_path_dir = os.path.dirname(rel_path)
        if not os.path.exists(self._get_cache_path(rel_path_dir)):
            os.makedirs(self._get_cache_path(rel_path_dir), exist_ok=True)
        # Now pull in the file
        dest = self._get_cache_path(rel_path)
        file_ok = self.rucio_broker.download(rel_path, dest, auth_token)
        self._fix_permissions(self._get_cache_path(rel_path_dir))
        return file_ok

    def _fix_file_permissions(self, path):
        umask_fix_perms(path, self.config.umask, 0o666)

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
        rel_path = self._construct_path(obj, **kwargs)
        log.debug("rucio _exists: " + rel_path)

        dir_only = kwargs.get("dir_only", False)
        base_dir = kwargs.get("base_dir", None)

        # Check cache and rucio
        if self._in_cache(rel_path) or (not dir_only and self.rucio_broker.data_object_exists(rel_path)):
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
        log.debug("rucio file_ready")
        """
        A helper method that checks if a file corresponding to a dataset is
        ready and available to be used. Return ``True`` if so, ``False`` otherwise.
        """
        rel_path = self._construct_path(obj, **kwargs)
        # Make sure the size in cache is available in its entirety
        if self._in_cache(rel_path):
            if os.path.getsize(self._get_cache_path(rel_path)) == self.rucio_broker.get_size(rel_path):
                return True
        log.debug(
            "Waiting for dataset %s to transfer from OS: %s/%s",
            rel_path,
            os.path.getsize(self._get_cache_path(rel_path)),
            self.rucio_broker.get_size(rel_path),
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
                # need this line to set the dataset filename, not sure how this is done - filesystem is monitored?
                open(os.path.join(self.staging_path, rel_path), "w").close()
            log.debug("rucio _create: " + rel_path)

    def _empty(self, obj, **kwargs):
        log.debug("rucio _empty")
        if self._exists(obj, **kwargs):
            return bool(self._size(obj, **kwargs) > 0)
        else:
            raise ObjectNotFound(f"objectstore.empty, object does not exist: {obj}, kwargs: {kwargs}")

    def _size(self, obj, **kwargs):
        rel_path = self._construct_path(obj, **kwargs)
        log.debug("rucio _size: " + rel_path)

        if self._in_cache(rel_path):
            try:
                size = os.path.getsize(self._get_cache_path(rel_path))
            except OSError as ex:
                log.info("Could not get size of file '%s' in local cache, will try iRODS. Error: %s", rel_path, ex)
            if size != 0:
                return size
        if self._exists(obj, **kwargs):
            return self.rucio_broker.get_size(rel_path)
        log.warning("Did not find dataset '%s', returning 0 for size", rel_path)
        return 0

    def _delete(self, obj, entire_dir=False, **kwargs):
        rel_path = self._construct_path(obj, **kwargs)
        extra_dir = kwargs.get("extra_dir", None)
        base_dir = kwargs.get("base_dir", None)
        dir_only = kwargs.get("dir_only", False)
        obj_dir = kwargs.get("obj_dir", False)
        log.debug("rucio _delete: " + rel_path)

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

            # Delete from rucio as well
            if self.rucio_broker.data_object_exists(rel_path):
                self.rucio_broker.delete(rel_path)
                return True
        except OSError:
            log.exception("%s delete error", self._get_filename(obj, **kwargs))
        return False

    def _get_data(self, obj, start=0, count=-1, **kwargs):
        rel_path = self._construct_path(obj, **kwargs)
        log.debug("rucio _get_data: " + rel_path)
        auth_token = self._get_token(**kwargs)
        # Check cache first and get file if not there
        if not self._in_cache(rel_path) or os.path.getsize(self._get_cache_path(rel_path)) == 0:
            self._pull_into_cache(rel_path, auth_token)
        # Read the file content from cache
        data_file = open(self._get_cache_path(rel_path))
        data_file.seek(start)
        content = data_file.read(count)
        data_file.close()
        return content

    def _get_token(self, **kwargs):
        auth_token = kwargs.get("auth_token", None)
        if auth_token:
            return auth_token
        try:
            trans = kwargs.get("trans", None)
            backend = provider_name_to_backend(self.oidc_provider)
            tokens = trans.user.get_oidc_tokens(backend)
            return tokens["id"]
        except Exception as e:
            log.debug("Failed to get auth token: %s", e)
            return None

    def _update_cache(self, obj, **kwargs):
        base_dir = kwargs.get("base_dir", None)
        dir_only = kwargs.get("dir_only", False)
        auth_token = self._get_token(**kwargs)
        rel_path = self._construct_path(obj, **kwargs)
        log.debug("rucio _update_cache: " + rel_path)

        # for JOB_WORK directory
        if base_dir and dir_only:
            return os.path.abspath(rel_path)

        cache_path = self._get_cache_path(rel_path)
        in_cache = self._in_cache(rel_path)
        size_in_cache = 0
        if in_cache:
            size_in_cache = os.path.getsize(self._get_cache_path(rel_path))

        # return path if we do not need to update cache
        if in_cache and dir_only:
            return cache_path
        # something is already in cache
        elif in_cache:
            size_in_rdb = self.rucio_broker.get_size(rel_path)
            # same size as in  rucio, or empty file in rucio - do not pull
            if size_in_cache == size_in_rdb or size_in_rdb == 0:
                return cache_path

        # Check if the file exists in persistent storage and, if it does, pull it into cache
        if self._exists(obj, **kwargs):
            if dir_only:  # Directories do not get pulled into cache
                return cache_path
            else:
                if self._pull_into_cache(rel_path, auth_token):
                    return cache_path
        raise ObjectNotFound(f"objectstore.get_filename, no cache_path: {obj}, kwargs: {kwargs}")

    def _get_filename(self, obj, **kwargs):
        base_dir = kwargs.get("base_dir", None)
        dir_only = kwargs.get("dir_only", False)
        rel_path = self._construct_path(obj, **kwargs)
        log.debug("rucio _get_filename: " + rel_path)

        # for JOB_WORK directory
        if base_dir and dir_only:
            return os.path.abspath(rel_path)

        return self._get_cache_path(rel_path)

    def _register_file(self, rel_path, file_name):
        if file_name is None:
            file_name = self._get_cache_path(rel_path)
            if not os.path.islink(file_name):
                raise ObjectInvalid(
                    f"rucio objectstore._register_file, rucio_register_only "
                    f"is set, but file in cache is not a link ")
        if os.path.islink(file_name):
            file_name = os.readlink(file_name)
        self.rucio_broker.register(rel_path, file_name)
        log.debug("rucio _register_file: " + file_name)
        return

    def _update_from_file(self, obj, file_name=None, create=False, **kwargs):
        if not create:
            raise ObjectNotFound(f"rucio objectstore.update_from_file, file update not allowed")
        rel_path = self._construct_path(obj, **kwargs)

        if self.rucio_config["rucio_register_only"]:
            self._register_file(rel_path, file_name)
            return

        log.debug("rucio _update_from_file:" + rel_path)

        # Choose whether to use the dataset file itself or an alternate file
        if file_name:
            source_file = os.path.abspath(file_name)
            # Copy into cache
            cache_file = self._get_cache_path(rel_path)
            try:
                if source_file != cache_file:
                    try:
                        shutil.copy2(source_file, cache_file)
                    except OSError:
                        os.makedirs(os.path.dirname(cache_file))
                        shutil.copy2(source_file, cache_file)
                self._fix_file_permissions(cache_file)
                source_file = cache_file
            except OSError:
                log.exception("Trouble copying source file '%s' to cache '%s'", source_file, cache_file)
        else:
            source_file = self._get_cache_path(rel_path)

        # Update the file on rucio
        self.rucio_broker.upload(rel_path, source_file)

    def _get_store_usage_percent(self, **kwargs):
        log.debug("rucio _get_store_usage_percent, not implemented yet")
        return 0.0

    def _get_object_url(self, obj, extra_dir=None, extra_dir_at_root=False, alt_name=None):
        log.debug("rucio _get_object_url")
        return None

    def __build_kwargs(self, obj, **kwargs):
        kwargs["object_id"] = obj.id
        return kwargs

    def shutdown(self):
        pass
