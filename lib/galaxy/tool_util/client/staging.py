"""Client for staging inputs for Galaxy Tools and Workflows.

Implement as a connector to serve a bridge between galactic_job_json
utility and a Galaxy API library.
"""
import abc
import json
import logging
import os

import yaml

from galaxy.tool_util.cwl.util import (
    DirectoryUploadTarget,
    FileLiteralTarget,
    FileUploadTarget,
    galactic_job_json,
    path_or_uri_to_uri,
)

log = logging.getLogger(__name__)

UPLOAD_TOOL_ID = "upload1"
LOAD_TOOLS_FROM_PATH = True
DEFAULT_USE_FETCH_API = True
DEFAULT_FILE_TYPE = "auto"
DEFAULT_DBKEY = "?"


class StagingInterace(metaclass=abc.ABCMeta):
    """Client that parses a job input and populates files into the Galaxy API.

    Abstract class that must override _post (and optionally other things such
    _attach_file, _log, etc..) to adapt to bioblend (for Planemo) or using the
    tool test interactor infrastructure.
    """

    @abc.abstractmethod
    def _post(self, api_path, payload, files_attached=False):
        """Make a post to the Galaxy API along supplied path."""

    def _attach_file(self, path):
        return open(path, 'rb')

    def _tools_post(self, payload, files_attached=False):
        tool_response = self._post("tools", payload, files_attached=files_attached)
        for job in tool_response.get("jobs", []):
            self._handle_job(job)
        return tool_response

    def _fetch_post(self, payload, files_attached=False):
        tool_response = self._post("tools/fetch", payload, files_attached=files_attached)
        for job in tool_response.get("jobs", []):
            self._handle_job(job)
        return tool_response

    def _handle_job(self, job_response):
        """Implementer can decide if to wait for job(s) individually or not here."""

    def stage(self, tool_or_workflow, history_id, job=None, job_path=None, use_path_paste=LOAD_TOOLS_FROM_PATH, to_posix_lines=True, job_dir="."):
        files_attached = [False]

        def upload_func_fetch(upload_target):

            def _attach_file(upload_payload, uri, index=0):
                uri = path_or_uri_to_uri(uri)
                is_path = uri.startswith("file://")
                if not is_path or use_path_paste:
                    return {"src": "url", "url": uri}
                else:
                    files_attached[0] = True
                    path = uri[len("file://"):]
                    upload_payload["__files"][f"files_{index}|file_data"] = self._attach_file(path)
                    return {"src": "files"}

            fetch_payload = None
            if isinstance(upload_target, FileUploadTarget):
                file_path = upload_target.path
                file_type = upload_target.properties.get('filetype', None) or DEFAULT_FILE_TYPE
                dbkey = upload_target.properties.get('dbkey', None) or DEFAULT_DBKEY
                fetch_payload = _fetch_payload(
                    history_id,
                    file_type=file_type,
                    dbkey=dbkey,
                    to_posix_lines=to_posix_lines,
                )
                name = _file_path_to_name(file_path)
                if file_path is not None:
                    src = _attach_file(fetch_payload, file_path)
                    fetch_payload["targets"][0]["elements"][0].update(src)

                if upload_target.composite_data:
                    composite_items = []
                    for i, composite_data in enumerate(upload_target.composite_data):
                        composite_item_src = _attach_file(fetch_payload, composite_data, index=i)
                        composite_items.append(composite_item_src)
                    fetch_payload["targets"][0]["elements"][0]["src"] = "composite"
                    fetch_payload["targets"][0]["elements"][0]["composite"] = {
                        "items": composite_items,
                    }

                tags = upload_target.properties.get("tags")
                if tags:
                    fetch_payload["targets"][0]["elements"][0]["tags"] = tags
                fetch_payload["targets"][0]["elements"][0]["name"] = name
            elif isinstance(upload_target, FileLiteralTarget):
                fetch_payload = _fetch_payload(history_id)
                # For file literals - take them as is - never convert line endings.
                fetch_payload["targets"][0]["elements"][0].update({
                    "src": "pasted",
                    "paste_content": upload_target.contents,
                    "to_posix_lines": False,
                })
                tags = upload_target.properties.get("tags")
                if tags:
                    fetch_payload["targets"][0]["elements"][0]["tags"] = tags
            elif isinstance(upload_target, DirectoryUploadTarget):
                fetch_payload = _fetch_payload(history_id, file_type="directory")
                fetch_payload["targets"][0].pop("elements")
                tar_path = upload_target.path
                src = _attach_file(fetch_payload, tar_path)
                fetch_payload["targets"][0]["elements_from"] = src
            else:
                content = json.dumps(upload_target.object)
                fetch_payload = _fetch_payload(history_id, file_type="expression.json")
                fetch_payload["targets"][0]["elements"][0].update({
                    "src": "pasted",
                    "paste_content": content,
                })
                tags = upload_target.properties.get("tags")
                fetch_payload["targets"][0]["elements"][0]["tags"] = tags
            return self._fetch_post(fetch_payload, files_attached=files_attached[0])

        # Save legacy upload_func to target older Galaxy servers
        def upload_func(upload_target):

            def _attach_file(upload_payload, uri, index=0):
                uri = path_or_uri_to_uri(uri)
                is_path = uri.startswith("file://")
                if not is_path or use_path_paste:
                    upload_payload["inputs"]["files_%d|url_paste" % index] = uri
                else:
                    files_attached[0] = True
                    path = uri[len("file://"):]
                    upload_payload["__files"]["files_%d|file_data" % index] = self._attach_file(path)

            if isinstance(upload_target, FileUploadTarget):
                file_path = upload_target.path
                file_type = upload_target.properties.get('filetype', None) or DEFAULT_FILE_TYPE
                dbkey = upload_target.properties.get('dbkey', None) or DEFAULT_DBKEY
                upload_payload = _upload_payload(
                    history_id,
                    file_type=file_type,
                    to_posix_lines=dbkey,
                )
                name = _file_path_to_name(file_path)
                upload_payload["inputs"]["files_0|auto_decompress"] = False
                upload_payload["inputs"]["auto_decompress"] = False
                if file_path is not None:
                    _attach_file(upload_payload, file_path)
                upload_payload["inputs"]["files_0|NAME"] = name
                if upload_target.secondary_files:
                    _attach_file(upload_payload, upload_target.secondary_files, index=1)
                    upload_payload["inputs"]["files_1|type"] = "upload_dataset"
                    upload_payload["inputs"]["files_1|auto_decompress"] = True
                    upload_payload["inputs"]["file_count"] = "2"
                    upload_payload["inputs"]["force_composite"] = "True"
                # galaxy.exceptions.RequestParameterInvalidException: Not input source type
                # defined for input '{'class': 'File', 'filetype': 'imzml', 'composite_data':
                # ['Example_Continuous.imzML', 'Example_Continuous.ibd']}'.\n"}]]

                if upload_target.composite_data:
                    for i, composite_data in enumerate(upload_target.composite_data):
                        upload_payload["inputs"][f"files_{i}|type"] = "upload_dataset"
                        _attach_file(upload_payload, composite_data, index=i)

                self._log(f"upload_payload is {upload_payload}")
                return self._tools_post(upload_payload, files_attached=files_attached[0])
            elif isinstance(upload_target, FileLiteralTarget):
                # For file literals - take them as is - never convert line endings.
                payload = _upload_payload(history_id, file_type="auto", auto_decompress=False, to_posix_lines=False)
                payload["inputs"]["files_0|url_paste"] = upload_target.contents
                return self._tools_post(payload)
            elif isinstance(upload_target, DirectoryUploadTarget):
                tar_path = upload_target.tar_path

                upload_payload = _upload_payload(
                    history_id,
                    file_type="tar",
                )
                upload_payload["inputs"]["files_0|auto_decompress"] = False
                _attach_file(upload_payload, tar_path)
                tar_upload_response = self._tools_post(upload_payload, files_attached=files_attached[0])
                convert_payload = dict(
                    tool_id="CONVERTER_tar_to_directory",
                    tool_inputs={"input1": {"src": "hda", "id": tar_upload_response["outputs"][0]["id"]}},
                    history_id=history_id,
                )
                convert_response = self._tools_post(convert_payload)
                assert "outputs" in convert_response, convert_response
                return convert_response
            else:
                content = json.dumps(upload_target.object)
                payload = _upload_payload(history_id, file_type="expression.json")
                payload["files_0|url_paste"] = content
                return self._tools_post(payload)

        def create_collection_func(element_identifiers, collection_type):
            payload = {
                "name": "dataset collection",
                "instance_type": "history",
                "history_id": history_id,
                "element_identifiers": element_identifiers,
                "collection_type": collection_type,
                "fields": None if collection_type != "record" else "auto",
            }
            return self._post("dataset_collections", payload)

        if job_path is not None:
            assert job is None
            with open(job_path) as f:
                job = yaml.safe_load(f)
            job_dir = os.path.dirname(os.path.abspath(job_path))
        else:
            assert job is not None
            assert job_dir is not None

        if self.use_fetch_api:
            upload = upload_func_fetch
        else:
            upload = upload_func

        job_dict, datasets = galactic_job_json(
            job,
            job_dir,
            upload,
            create_collection_func,
            tool_or_workflow,
        )
        return job_dict, datasets

    # extension point for planemo to override logging
    def _log(self, message):
        log.debug(message)

    @abc.abstractproperty
    def use_fetch_api(self):
        """Return true is this should use (modern) data fetch API."""


class InteractorStaging(StagingInterace):

    def __init__(self, galaxy_interactor, use_fetch_api=DEFAULT_USE_FETCH_API):
        self.galaxy_interactor = galaxy_interactor
        self._use_fetch_api = use_fetch_api

    def _post(self, api_path, payload, files_attached=False):
        response = self.galaxy_interactor._post(api_path, payload, json=True)
        assert response.status_code == 200, response.text
        return response.json()

    def _handle_job(self, job_response):
        self.galaxy_interactor.wait_for_job(job_response["id"])

    @property
    def use_fetch_api(self):
        return self._use_fetch_api


def _file_path_to_name(file_path):
    if file_path is not None:
        name = os.path.basename(file_path)
    else:
        name = "defaultname"
    return name


def _upload_payload(history_id, tool_id=UPLOAD_TOOL_ID, file_type=DEFAULT_FILE_TYPE, dbkey=DEFAULT_DBKEY, **kwd):
    """Adapted from bioblend tools client."""
    payload = {}
    payload["history_id"] = history_id
    payload["tool_id"] = tool_id
    tool_input = {}
    tool_input["file_type"] = file_type
    tool_input["dbkey"] = dbkey
    if not kwd.get('to_posix_lines', True):
        tool_input['files_0|to_posix_lines'] = False
    elif kwd.get('space_to_tab', False):
        tool_input['files_0|space_to_tab'] = 'Yes'
    if 'file_name' in kwd:
        tool_input["files_0|NAME"] = kwd['file_name']
    tool_input["files_0|type"] = "upload_dataset"
    payload["inputs"] = tool_input
    payload["__files"] = {}
    return payload


def _fetch_payload(history_id, file_type=DEFAULT_FILE_TYPE, dbkey=DEFAULT_DBKEY, **kwd):
    element = {
        "ext": file_type,
        "dbkey": dbkey,
    }
    for arg in ['to_posix_lines', 'space_to_tab']:
        if arg in kwd:
            element[arg] = kwd[arg]
    if 'file_name' in kwd:
        element['name'] = kwd['file_name']
    target = {
        "destination": {"type": "hdas"},
        "elements": [element],
        "auto_decompress": False,
    }
    targets = [target]
    payload = {
        "history_id": history_id,
        "targets": targets,
        "__files": {}
    }
    return payload
