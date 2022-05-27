import textwrap
import zipfile
from io import BytesIO

from galaxy_test.base.populators import (
    DatasetCollectionPopulator,
    DatasetPopulator,
    skip_without_datatype,
    skip_without_tool,
)
from ._framework import ApiTestCase


class DatasetsApiTestCase(ApiTestCase):
    history_id: str

    def setUp(self):
        super().setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)
        self.dataset_collection_populator = DatasetCollectionPopulator(self.galaxy_interactor)
        self.history_id = self.dataset_populator.new_history()

    def test_index(self):
        index_response = self._get("datasets")
        self._assert_status_code_is(index_response, 200)

    def test_search_datasets(self):
        hda_id = self.dataset_populator.new_dataset(self.history_id)['id']
        payload = {'limit': 1, 'offset': 0}
        index_response = self._get("datasets", payload).json()
        assert len(index_response) == 1
        assert index_response[0]['id'] == hda_id
        hdca_id = self.dataset_collection_populator.create_list_in_history(self.history_id,
                                                                           contents=["1\n2\n3"]).json()['id']
        index_payload_1 = {'limit': 3, 'offset': 0}
        index_response = self._get("datasets", index_payload_1).json()
        assert len(index_response) == 3
        assert index_response[0]['id'] == hdca_id
        assert index_response[0]['history_content_type'] == 'dataset_collection'
        assert index_response[2]['id'] == hda_id
        assert index_response[2]['history_content_type'] == 'dataset'
        index_payload_2 = {'limit': 2, 'offset': 0, 'q': ['history_content_type'], 'qv': ['dataset']}
        index_response = self._get("datasets", index_payload_2).json()
        assert index_response[1]['id'] == hda_id

    def test_search_by_tag(self):
        hda_id = self.dataset_populator.new_dataset(self.history_id)['id']
        update_payload = {
            'tags': ['cool:new_tag', 'cool:another_tag'],
        }
        updated_hda = self._put(
            f"histories/{self.history_id}/contents/{hda_id}",
            update_payload, json=True).json()
        assert 'cool:new_tag' in updated_hda['tags']
        assert 'cool:another_tag' in updated_hda['tags']
        payload = {'limit': 10, 'offset': 0, 'q': ['history_content_type', 'tag'], 'qv': ['dataset', 'cool:new_tag']}
        index_response = self._get("datasets", payload).json()
        assert len(index_response) == 1
        payload = {'limit': 10, 'offset': 0, 'q': ['history_content_type', 'tag-contains'],
                   'qv': ['dataset', 'new_tag']}
        index_response = self._get("datasets", payload).json()
        assert len(index_response) == 1
        payload = {'limit': 10, 'offset': 0, 'q': ['history_content_type', 'tag-contains'], 'qv': ['dataset', 'notag']}
        index_response = self._get("datasets", payload).json()
        assert len(index_response) == 0

    def test_search_by_tool_id(self):
        self.dataset_populator.new_dataset(self.history_id)
        payload = {'limit': 1, 'offset': 0, 'q': ['history_content_type', 'tool_id'], 'qv': ['dataset', 'upload1']}
        assert len(self._get("datasets", payload).json()) == 1
        payload = {'limit': 1, 'offset': 0, 'q': ['history_content_type', 'tool_id'], 'qv': ['dataset', 'uploadX']}
        assert len(self._get("datasets", payload).json()) == 0
        payload = {'limit': 1, 'offset': 0, 'q': ['history_content_type', 'tool_id-contains'], 'qv': ['dataset', 'pload1']}
        assert len(self._get("datasets", payload).json()) == 1
        self.dataset_collection_populator.create_list_in_history(self.history_id,
                                                                 name="search by tool id",
                                                                 contents=["1\n2\n3"]).json()
        self.dataset_populator.wait_for_history(self.history_id)
        payload = {'limit': 10, 'offset': 0, 'history_id': self.history_id, 'q': ['name', 'tool_id'],
                   'qv': ['search by tool id', 'upload1']}
        result = self._get("datasets", payload).json()
        assert result[0]['name'] == 'search by tool id', result
        payload = {'limit': 1, 'offset': 0, 'q': ['history_content_type', 'tool_id'],
                   'qv': ['dataset_collection', 'uploadX']}
        result = self._get("datasets", payload).json()
        assert len(result) == 0

    def test_invalid_search(self):
        payload = {'limit': 10, 'offset': 0, 'q': ['history_content_type', 'tag-invalid_op'], 'qv': ['dataset', 'notag']}
        index_response = self._get("datasets", payload)
        self._assert_status_code_is(index_response, 400)
        assert index_response.json()['err_msg'] == 'bad op in filter'

    def test_search_returns_only_accessible(self):
        hda_id = self.dataset_populator.new_dataset(self.history_id)['id']
        with self._different_user():
            payload = {'limit': 10, 'offset': 0, 'q': ['history_content_type'], 'qv': ['dataset']}
            index_response = self._get("datasets", payload).json()
            for item in index_response:
                assert hda_id != item['id']

    def test_show(self):
        hda1 = self.dataset_populator.new_dataset(self.history_id)
        show_response = self._get(f"datasets/{hda1['id']}")
        self._assert_status_code_is(show_response, 200)
        self.__assert_matches_hda(hda1, show_response.json())

    def test_show_permission_denied(self):
        hda = self.dataset_populator.new_dataset(self.history_id)
        self.dataset_populator.make_private(history_id=self.history_id, dataset_id=hda['id'])
        with self._different_user():
            show_response = self._get(f"datasets/{hda['id']}")
            self._assert_status_code_is(show_response, 403)

    def test_admin_can_update_permissions(self):
        # Create private dataset
        hda = self.dataset_populator.new_dataset(self.history_id)
        dataset_id = hda['id']
        self.dataset_populator.make_private(history_id=self.history_id, dataset_id=dataset_id)

        # Admin removes restrictions
        payload = {"action": "remove_restrictions"}
        update_response = self._put(f"datasets/{dataset_id}/permissions", payload, admin=True, json=True)
        self._assert_status_code_is_ok(update_response)

        # Other users can access the dataset
        with self._different_user():
            show_response = self._get(f"datasets/{hda['id']}")
            self._assert_status_code_is_ok(show_response)

    def __assert_matches_hda(self, input_hda, query_hda):
        self._assert_has_keys(query_hda, "id", "name")
        assert input_hda["name"] == query_hda["name"]
        assert input_hda["id"] == query_hda["id"]

    def test_display(self):
        contents = textwrap.dedent("""\
        1   2   3   4
        A   B   C   D
        10  20  30  40
        """)
        hda1 = self.dataset_populator.new_dataset(self.history_id, content=contents)
        self.dataset_populator.wait_for_history(self.history_id)
        display_response = self._get(f"histories/{self.history_id}/contents/{hda1['id']}/display", {
            'raw': 'True'
        })
        self._assert_status_code_is(display_response, 200)
        assert display_response.text == contents

    def test_tag_change(self):
        hda_id = self.dataset_populator.new_dataset(self.history_id)['id']
        payload = {
            'item_id': hda_id,
            'item_class': 'HistoryDatasetAssociation',
            'item_tags': ['cool:tag_a', 'cool:tag_b', 'tag_c', 'name:tag_d', '#tag_e'],
        }

        put_response = self._put("tags", data=payload, json=True)
        self._assert_status_code_is_ok(put_response)
        updated_hda = self._get(
            f"histories/{self.history_id}/contents/{hda_id}").json()
        assert 'cool:tag_a' in updated_hda['tags']
        assert 'cool:tag_b' in updated_hda['tags']
        assert 'tag_c' in updated_hda['tags']
        assert 'name:tag_d' in updated_hda['tags']
        assert 'name:tag_e' in updated_hda['tags']

    @skip_without_tool("cat_data_and_sleep")
    def test_update_datatype(self):
        hda_id = self.dataset_populator.new_dataset(self.history_id)['id']
        original_hda = self._get(
            f"histories/{self.history_id}/contents/{hda_id}").json()
        assert original_hda['extension'] == 'txt'
        assert original_hda['data_type'] == 'galaxy.datatypes.data.Text'
        assert 'scatterplot' not in [viz['name'] for viz in original_hda['visualizations']]

        inputs = {
            'input1': {'src': 'hda', 'id': hda_id},
            'sleep_time': 10,
        }
        run_response = self.dataset_populator.run_tool_raw(
            "cat_data_and_sleep",
            inputs,
            self.history_id,
        )
        queued_id = run_response.json()["outputs"][0]["id"]

        update_while_incomplete_response = self._put(  # try updating datatype while used as output of a running job
            f"histories/{self.history_id}/contents/{queued_id}",
            data={'datatype': 'tabular'}, json=True)
        self._assert_status_code_is(update_while_incomplete_response, 400)

        self.dataset_populator.wait_for_history_jobs(self.history_id)  # now wait for upload to complete

        successful_updated_hda_response = self._put(
            f"histories/{self.history_id}/contents/{hda_id}",
            data={'datatype': 'tabular'}, json=True).json()
        assert successful_updated_hda_response['extension'] == 'tabular'
        assert successful_updated_hda_response['data_type'] == 'galaxy.datatypes.tabular.Tabular'
        assert 'scatterplot' in [viz['name'] for viz in successful_updated_hda_response['visualizations']]

        invalidly_updated_hda_response = self._put(  # try updating with invalid datatype
            f"histories/{self.history_id}/contents/{hda_id}",
            data={'datatype': 'invalid'}, json=True)
        self._assert_status_code_is(invalidly_updated_hda_response, 400)

    @skip_without_datatype("velvet")
    def test_composite_datatype_download(self):
        item = {
            "src": "composite",
            "ext": "velvet",
            "composite": {
                "items": [
                    {"src": "pasted", "paste_content": "sequences content"},
                    {"src": "pasted", "paste_content": "roadmaps content"},
                    {"src": "pasted", "paste_content": "log content"},
                ]
            },
        }
        output = self.dataset_populator.fetch_hda(self.history_id, item, wait=True)
        print(output)
        response = self._get(f"histories/{self.history_id}/contents/{output['id']}/display?to_ext=zip")
        self._assert_status_code_is(response, 200)
        archive = zipfile.ZipFile(BytesIO(response.content))
        namelist = archive.namelist()
        assert len(namelist) == 4, f"Expected 3 elements in [{namelist}]"
