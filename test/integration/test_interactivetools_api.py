"""Integration tests for realtime tools."""
import os
import tempfile

import pytest
import requests

from galaxy_test.base import api_asserts
from galaxy_test.base.populators import (
    DatasetPopulator,
    wait_on,
)
from galaxy_test.driver import integration_util
from .test_containerized_jobs import (
    ContainerizedIntegrationTestCase,
    disable_dependency_resolution,
    DOCKERIZED_JOB_CONFIG_FILE,
)
from .test_kubernetes_staging import (
    CONTAINERIZED_TEMPLATE,
    job_config,
    set_infrastucture_url,
)

SCRIPT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
EMBEDDED_PULSAR_JOB_CONFIG_FILE_DOCKER = os.path.join(SCRIPT_DIRECTORY, "embedded_pulsar_docker_job_conf.yml")


class BaseInteractiveToolsIntegrationTestCase(ContainerizedIntegrationTestCase):
    framework_tool_and_types = True
    container_type = "docker"
    require_uwsgi = True
    enable_realtime_mapping = True

    def setUp(self):
        super().setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)
        self.history_id = self.dataset_populator.new_history()

    # Move helpers to populators.py
    def wait_on_proxied_content(self, target):
        def get_hosted_content():
            try:
                scheme, rest = target.split("://", 1)
                prefix, host_and_port = rest.split(".interactivetool.")
                faked_host = rest
                if "/" in rest:
                    faked_host = rest.split("/", 1)[0]
                url = f"{scheme}://{host_and_port}"
                response = requests.get(url, timeout=1, headers={"Host": faked_host})
                return response.text
            except Exception as e:
                print(e)
                return None

        content = wait_on(get_hosted_content, "realtime hosted content at %s" % target)
        return content

    def entry_point_target(self, entry_point_id):
        entry_point_access_response = self._get("entry_points/%s/access" % entry_point_id)
        api_asserts.assert_status_code_is(entry_point_access_response, 200)
        access_json = entry_point_access_response.json()
        api_asserts.assert_has_key(access_json, "target")
        return access_json["target"]

    def wait_on_entry_points_active(self, job_id, expected_num=1):
        def active_entry_points():
            entry_points = self.entry_points_for_job(job_id)
            if len(entry_points) != expected_num:
                return None
            elif any(not e["active"] for e in entry_points):
                job_json = self._get(f"jobs/{job_id}?full=true").json()
                if job_json['state'] == 'error':
                    raise Exception(f"Interactive tool job {job_id} failed: {job_json}")
                return None
            else:
                return entry_points

        # It currently takes at least 90 seconds until we can be sure the container monitor failed.
        # Can be decreased when galaxy_ext/container_monitor/monitor.py changes
        return wait_on(active_entry_points, "entry points to become active", timeout=120)

    def entry_points_for_job(self, job_id):
        entry_points_response = self._get("entry_points?job_id=%s" % job_id)
        api_asserts.assert_status_code_is(entry_points_response, 200)
        return entry_points_response.json()


class RunsInterativeToolTests:

    def test_simple_execution(self):
        response_dict = self.dataset_populator.run_tool("interactivetool_simple", {}, self.history_id)
        assert "jobs" in response_dict, response_dict
        jobs = response_dict["jobs"]
        assert isinstance(jobs, list)
        assert len(jobs) == 1
        job0 = jobs[0]
        entry_points = self.wait_on_entry_points_active(job0["id"])
        assert len(entry_points) == 1
        entry_point0 = entry_points[0]
        target = self.entry_point_target(entry_point0["id"])
        content = self.wait_on_proxied_content(target)
        assert content == "moo cow\n", content

    def test_multi_server_realtime_tool(self):
        response_dict = self.dataset_populator.run_tool("interactivetool_two_entry_points", {}, self.history_id)
        assert "jobs" in response_dict, response_dict
        jobs = response_dict["jobs"]
        assert isinstance(jobs, list)
        assert len(jobs) == 1
        job0 = jobs[0]
        entry_points = self.wait_on_entry_points_active(job0["id"], expected_num=2)
        entry_point0 = entry_points[0]
        entry_point1 = entry_points[1]
        target0 = self.entry_point_target(entry_point0["id"])
        target1 = self.entry_point_target(entry_point1["id"])
        assert target0 != target1
        content0 = self.wait_on_proxied_content(target0)
        assert content0 == "moo cow\n", content0

        content1 = self.wait_on_proxied_content(target1)
        assert content1 == "moo cow\n", content1
        stop_response = self.dataset_populator._delete(f'entry_points/{entry_point0["id"]}')
        stop_response.raise_for_status()
        self.dataset_populator.wait_for_job(job0['id'], assert_ok=True)
        job_details = self.dataset_populator.get_job_details(job0['id'], full=True)
        job_details.raise_for_status()
        job_details = job_details.json()
        assert job_details['state'] == 'ok'
        it_output_details = self.dataset_populator.get_history_dataset_details_raw(self.history_id, dataset_id=job_details['outputs']['test_output']['id'])
        it_output_details.raise_for_status()
        it_output_details = it_output_details.json()
        assert it_output_details['state'] == 'ok'
        assert not it_output_details['deleted']


class InteractiveToolsIntegrationTestCase(BaseInteractiveToolsIntegrationTestCase, RunsInterativeToolTests):
    pass


class InteractiveToolsPulsarIntegrationTestCase(BaseInteractiveToolsIntegrationTestCase, RunsInterativeToolTests):

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        config["job_config_file"] = EMBEDDED_PULSAR_JOB_CONFIG_FILE_DOCKER
        config["galaxy_infrastructure_url"] = 'http://localhost:$UWSGI_PORT'
        disable_dependency_resolution(config)


class InteractiveToolsRemoteProxyIntegrationTestCase(BaseInteractiveToolsIntegrationTestCase, RunsInterativeToolTests):
    """
    $ cd gx-it-proxy
    $ ./lib/createdb.js --sessions $HOME/gxitexproxy.sqlite
    $ ./lib/main.js --port 9001 --ip 0.0.0.0 --verbose --sessions $HOME/gxitexproxy.sqlite
    $ # Need to create new DB for each test I think, duplicate IDs are the problem I think because each test starts at 1
    $ GALAXY_TEST_EXTERNAL_PROXY_HOST="localhost:9001" GALAXY_TEST_EXTERNAL_PROXY_MAP="$HOME/gxitexproxy.sqlite" pytest -s test/integration/test_interactivetools_api.py::InteractiveToolsRemoteProxyIntegrationTestCase
    """
    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        interactivetools_map = os.environ.get("GALAXY_TEST_EXTERNAL_PROXY_MAP")
        interactivetools_proxy_host = os.environ.get("GALAXY_TEST_EXTERNAL_PROXY_HOST")
        if not interactivetools_map or not interactivetools_proxy_host:
            pytest.skip(f"External proxy not configured for test [map={interactivetools_map},host={interactivetools_proxy_host}]")
        config["job_config_file"] = DOCKERIZED_JOB_CONFIG_FILE
        config["interactivetools_proxy_host"] = interactivetools_proxy_host
        config["interactivetools_map"] = interactivetools_map
        disable_dependency_resolution(config)


@integration_util.skip_unless_kubernetes()
@integration_util.skip_unless_amqp()
@integration_util.skip_if_github_workflow()
class KubeInteractiveToolsRemoteProxyIntegrationTestCase(BaseInteractiveToolsIntegrationTestCase, RunsInterativeToolTests):
    """
    $ git clone https://github.com/galaxyproject/gx-it-proxy.git $HOME/gx-it-proxy
    $ cd $HOME/gx-it-proxy/docker/k8s
    $ # Setup proxy inside K8 cluster with kubectl - including forwarding port 8910
    $ bash run.sh
    $ cd ../..  # back session.
    $ # Need new DB for every test.
    $ rm -rf $HOME/gxitk8proxy.sqlite
    $ ./lib/createdb.js --sessions $HOME/gxitk8proxy.sqlite
    $ ./lib/main.js --port 9002 --ip 0.0.0.0 --verbose --sessions $HOME/gxitk8proxy.sqlite --forwardIP localhost --forwardPort 8910 &
    $ cd back/to/galaxy
    $ GALAXY_TEST_K8S_EXTERNAL_PROXY_HOST="localhost:9002" GALAXY_TEST_K8S_EXTERNAL_PROXY_MAP="$HOME/gxitk8proxy.sqlite" pytest -s test/integration/test_interactivetools_api.py::KubeInteractiveToolsRemoteProxyIntegrationTestCase
    """
    require_uwsgi = True

    @classmethod
    def setUpClass(cls):
        # realpath for docker deployed in a VM on Mac, also done in driver_util.
        cls.jobs_directory = os.path.realpath(tempfile.mkdtemp())
        super().setUpClass()

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        interactivetools_map = os.environ.get("GALAXY_TEST_K8S_EXTERNAL_PROXY_MAP")
        interactivetools_proxy_host = os.environ.get("GALAXY_TEST_K8S_EXTERNAL_PROXY_HOST")
        if not interactivetools_map or not interactivetools_proxy_host:
            pytest.skip(f"External proxy not configured for test [map={interactivetools_map},host={interactivetools_proxy_host}]")

        config["interactivetools_proxy_host"] = interactivetools_proxy_host
        config["interactivetools_map"] = interactivetools_map

        config["jobs_directory"] = cls.jobs_directory
        config["file_path"] = cls.jobs_directory
        config["job_config_file"] = job_config(CONTAINERIZED_TEMPLATE, cls.jobs_directory)
        config["default_job_shell"] = '/bin/sh'

        set_infrastucture_url(config)
        disable_dependency_resolution(config)
