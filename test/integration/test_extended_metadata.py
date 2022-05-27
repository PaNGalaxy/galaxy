"""Integration tests for the Pulsar embedded runner."""
import json

from galaxy_test.base.populators import DatasetPopulator
from galaxy_test.driver import integration_util
TEST_TOOL_IDS = [
    "job_properties",
    "multi_output",
    "multi_output_configured",
    "multi_output_assign_primary",
    "multi_output_assign_primary_ext_dbkey",
    "multi_output_recurse",
    "tool_provided_metadata_1",
    "tool_provided_metadata_2",
    "tool_provided_metadata_3",
    "tool_provided_metadata_4",
    "tool_provided_metadata_5",
    "tool_provided_metadata_6",
    "tool_provided_metadata_7",
    "tool_provided_metadata_8",
    "tool_provided_metadata_9",
    "tool_provided_metadata_10",
    "tool_provided_metadata_11",
    "tool_provided_metadata_12",
    "composite_output",
    "composite_output_tests",
    "metadata",
    "metadata_bam",
    "output_format",
    "output_auto_format",
    "collection_paired_test",
    "collection_paired_structured_like",
    "collection_nested_test",
    "collection_creates_list",
    "collection_creates_dynamic_nested",
    "collection_creates_dynamic_nested_from_json",
    "collection_creates_dynamic_nested_from_json_elements",
    "implicit_conversion",
    "environment_variables",
]


class ExtendedMetadataIntegrationTestCase(integration_util.IntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        config["metadata_strategy"] = "extended"
        config["tool_evaluation_strategy"] = "remote"
        config["object_store_store_by"] = "uuid"
        config["retry_metadata_internally"] = False

    def test_fetch_data(self):
        history_id = self.dataset_populator.new_history()
        element = dict(src="files")
        target = {
            "destination": {"type": "hdas"},
            "elements": [element],
        }
        targets = json.dumps([target])
        upload_content = 'abcdef'
        payload = {
            "history_id": history_id,
            "targets": targets,
            "__files": {"files_0|file_data": upload_content}
        }
        new_dataset = self.dataset_populator.fetch(payload, assert_ok=True).json()["outputs"][0]
        self.dataset_populator.wait_for_history(history_id, assert_ok=True)
        content = self.dataset_populator.get_history_dataset_content(
            history_id=history_id,
            dataset_id=new_dataset['id'],
        )
        assert content == upload_content


class ExtendedMetadataIntegrationInstance(integration_util.IntegrationInstance):
    """Describe a Galaxy test instance with embedded pulsar configured."""

    framework_tool_and_types = True

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        config["metadata_strategy"] = "extended"
        config["tool_evaluation_strategy"] = "remote"
        config["object_store_store_by"] = "uuid"
        config["retry_metadata_internally"] = False


instance = integration_util.integration_module_instance(ExtendedMetadataIntegrationInstance)

test_tools = integration_util.integration_tool_runner(TEST_TOOL_IDS)
