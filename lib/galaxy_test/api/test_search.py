from requests import delete

from galaxy_test.base.populators import WorkflowPopulator
from ._framework import ApiTestCase


class TestSearchApi(ApiTestCase):
    def test_search_workflows(self):
        workflow_populator = WorkflowPopulator(self.galaxy_interactor)
        workflow_id = workflow_populator.simple_workflow("test_for_search")
        search_response = self.__search("select * from workflow")
        assert self.__has_result_with_name(search_response, "test_for_search"), search_response.text

        # Deleted
        delete_url = self._api_url(f"workflows/{workflow_id}", use_key=True)
        delete(delete_url)

        search_response = self.__search("select * from workflow where deleted = False")
        assert not self.__has_result_with_name(search_response, "test_for_search"), search_response.text

    def __search(self, query):
        data = dict(query=query)
        search_response = self._post("search", data=data)
        self._assert_status_code_is(search_response, 200)
        return search_response

    def __has_result_with_name(self, search_response, name):
        search_response_object = search_response.json()
        assert "results" in search_response_object, search_response_object
        results = search_response_object["results"]
        return name in map(lambda r: r.get("name", None), results)
