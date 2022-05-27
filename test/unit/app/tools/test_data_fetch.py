import json
import os
from contextlib import contextmanager
from os import environ
from shutil import rmtree
from tempfile import mkdtemp

import pytest

from galaxy.tools.data_fetch import main

github_fetch = pytest.mark.skipif(
    not environ.get('GALAXY_TEST_INCLUDE_SLOW'),
    reason="GALAXY_TEST_INCLUDE_SLOW not set"
)


def test_simple_path_get():
    with _execute_context() as execute_context:
        job_directory = execute_context.job_directory
        example_path = os.path.join(job_directory, "example_file")
        with open(example_path, "w") as f:
            f.write("sample data\nhello world")
        request = {
            "targets": [
                {
                    "destination": {
                        "type": "hdas",
                    },
                    "elements": [
                        {
                            "src": "path",
                            "path": example_path
                        }
                    ]
                }
            ]
        }
        execute_context.execute_request(request)
        galaxy_json = execute_context.galaxy_json
        assert "__unnamed_outputs" in galaxy_json


def test_simple_list_path_get():
    with _execute_context() as execute_context:
        job_directory = execute_context.job_directory
        example_path = os.path.join(job_directory, "example_file")
        with open(example_path, "w") as f:
            f.write("sample data\nhello world")
        request = {
            "targets": [
                {
                    "destination": {
                        "type": "hdca",
                        "object_id": 76,
                    },
                    "elements": [
                        {
                            "src": "path",
                            "path": example_path
                        }
                    ]
                }
            ]
        }
        execute_context.execute_request(request)
        galaxy_json = execute_context.galaxy_json
        assert "__unnamed_outputs" in galaxy_json
        output = galaxy_json.get("__unnamed_outputs")[0]
        destination = output["destination"]
        assert "object_id" in destination
        assert destination["object_id"] == 76


@github_fetch
def test_hdas_single_url_error():
    with _execute_context() as execute_context:
        job_directory = execute_context.job_directory
        example_path = os.path.join(job_directory, "example_file")
        with open(example_path, "w") as f:
            f.write("sample data\nhello world")
        request = {
            "targets": [
                {
                    "destination": {
                        "type": "hdas",
                    },
                    "elements": [
                        {
                            "src": "path",
                            "path": example_path
                        },
                        {
                            "src": "url",
                            "url": "https://raw.githubusercontent.com/galaxyproject/galaxy/dev/test-data/12.bed"
                        }
                    ]
                }
            ]
        }
        execute_context.execute_request(request)
        galaxy_json = execute_context.galaxy_json
        assert "__unnamed_outputs" in galaxy_json
        output = galaxy_json.get("__unnamed_outputs")[0]
        assert "elements" in output
        elements = output["elements"]
        assert len(elements) == 2
        assert "error_message" not in elements[0]
        assert "error_message" in elements[1]
        error = elements[1]["error_message"]
        assert "Failed to fetch url https://raw.githubusercontent.com/galaxyproject/galaxy/dev/test-data/12.bed" in error


@github_fetch
def test_hdca_collection_element_failed():
    with _execute_context() as execute_context:
        job_directory = execute_context.job_directory
        example_path = os.path.join(job_directory, "example_file")
        with open(example_path, "w") as f:
            f.write("sample data\nhello world")
        request = {
            "targets": [
                {
                    "destination": {
                        "type": "hdca",
                    },
                    "elements": [
                        {
                            "src": "path",
                            "path": example_path
                        },
                        {
                            "src": "url",
                            "url": "https://raw.githubusercontent.com/galaxyproject/galaxy/dev/test-data/12.bed"
                        }
                    ]
                }
            ]
        }
        execute_context.execute_request(request)
        galaxy_json = execute_context.galaxy_json
        assert "__unnamed_outputs" in galaxy_json
        output = galaxy_json.get("__unnamed_outputs")[0]
        assert "error_message" in output
        error = output["error_message"]
        assert "Failed to fetch url https://raw.githubusercontent.com/galaxyproject/galaxy/dev/test-data/12.bed" in error


@github_fetch
def test_hdca_allow_failed_collections():
    with _execute_context() as execute_context:
        job_directory = execute_context.job_directory
        example_path = os.path.join(job_directory, "example_file")
        with open(example_path, "w") as f:
            f.write("sample data\nhello world")
        request = {
            "allow_failed_collections": True,
            "targets": [
                {
                    "destination": {
                        "type": "hdca",
                    },
                    "elements": [
                        {
                            "src": "path",
                            "path": example_path
                        },
                        {
                            "src": "url",
                            "url": "https://raw.githubusercontent.com/galaxyproject/galaxy/dev/test-data/12.bed"
                        }
                    ]
                }
            ]
        }
        execute_context.execute_request(request)
        galaxy_json = execute_context.galaxy_json
        assert "__unnamed_outputs" in galaxy_json
        output = galaxy_json.get("__unnamed_outputs")[0]
        assert "error_message" not in output
        assert "elements" in output
        elements = output["elements"]
        assert len(elements) == 2
        assert "error_message" not in elements[0]
        assert "error_message" in elements[1]
        error = elements[1]["error_message"]
        assert "Failed to fetch url https://raw.githubusercontent.com/galaxyproject/galaxy/dev/test-data/12.bed" in error


def test_hdca_failed_expansion():
    with _execute_context() as execute_context:
        job_directory = execute_context.job_directory
        example_path = os.path.join(job_directory, "example_file")
        with open(example_path, "w") as f:
            f.write("sample data\nhello world")
        request = {
            "targets": [
                {
                    "destination": {
                        "type": "hdca",
                        "object_id": 76,
                    },
                    "elements_from": "bagit",
                    "src": "path",
                    "path": example_path,
                }
            ]
        }
        execute_context.execute_request(request)
        galaxy_json = execute_context.galaxy_json
        assert "__unnamed_outputs" in galaxy_json
        output = galaxy_json.get("__unnamed_outputs")[0]
        assert "elements" in output
        elements = output["elements"]
        assert len(elements) == 0
        assert "error_message" in output
        assert "Expected bagit.txt does not exist" in output["error_message"]


@contextmanager
def _execute_context():
    job_directory = mkdtemp()
    try:
        yield ExecuteContext(job_directory)
    finally:
        rmtree(job_directory)


class ExecuteContext:

    def __init__(self, directory):
        self.job_directory = directory
        self.galaxy_json_path = os.path.join(directory, "galaxy.json")

    def execute_request(self, request):
        request_path = os.path.join(self.job_directory, "request.json")
        with open(request_path, "w") as f:
            json.dump(request, f)
        self._execute(["--request", request_path])

    def _execute(self, args):
        args.extend(["--working-directory", self.job_directory])
        assert not os.path.exists(self.galaxy_json_path)
        main(args)

    @property
    def galaxy_json(self):
        assert os.path.exists(self.galaxy_json_path)
        with open(self.galaxy_json_path) as f:
            return json.load(f)
