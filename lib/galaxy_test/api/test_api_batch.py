import json

from requests import post

from ._framework import ApiTestCase


class ApiBatchTestCase(ApiTestCase):

    def _get_api_key(self, admin=False):
        return self.galaxy_interactor.api_key if not admin else self.galaxy_interactor.master_api_key

    def _with_key(self, url, admin=False):
        sep = '&' if '?' in url else '?'
        return f"{url + sep}key={self._get_api_key(admin=admin)}"

    def _post_batch(self, batch):
        data = json.dumps({"batch": batch})
        return post(f"{self.galaxy_interactor.api_url}/batch", data=data)

    # ---- tests
    def test_simple_array(self):
        batch = [
            dict(url=self._with_key('/api/histories')),
            dict(url=self._with_key('/api/histories'),
                 method='POST', body=json.dumps(dict(name='Wat'))),
            dict(url=self._with_key('/api/histories')),
        ]
        response = self._post_batch(batch)
        response = response.json()
        self.assertIsInstance(response, list)
        self.assertEqual(len(response), 3)

    def test_unallowed_route(self):
        batch = [
            dict(url=self._with_key('/api/workflow'))
        ]
        response = self._post_batch(batch)
        response = response.json()
        self.assertIsInstance(response, list)
        self.assertEqual(response[0]['status'], 403)

    def test_404_route(self):
        # needs to be within the allowed routes
        batch = [
            dict(url=self._with_key('/api/histories_bler'))
        ]
        response = self._post_batch(batch)
        response = response.json()
        self.assertIsInstance(response, list)
        self.assertEqual(response[0]['status'], 404)

    def test_errors(self):
        batch = [
            dict(url=self._with_key('/api/histories/abc123')),
            dict(url=self._with_key('/api/jobs'), method='POST', body=json.dumps(dict(name='Wat'))),
        ]
        response = self._post_batch(batch)
        response = response.json()
        self.assertIsInstance(response, list)
        self.assertEqual(response[0]['status'], 400)
        self.assertEqual(response[1]['status'], 501)

    def test_querystring_params(self):
        post_data = dict(name='test')
        create_response = self._post('histories', data=post_data).json()

        history_url = f"/api/histories/{create_response['id']}"
        history_url_with_keys = f"{history_url}?v=dev&keys=size,non_ready_jobs"
        contents_url_with_filters = f"{history_url}/contents?v=dev&q=deleted&qv=True"
        batch = [
            dict(url=self._with_key(history_url_with_keys)),
            dict(url=self._with_key(contents_url_with_filters)),
        ]
        response = self._post_batch(batch)
        response = response.json()
        self.assertEqual(len(response), 2)
        self.assertEqual(len(response[0]['body'].keys()), 2)
        self.assertEqual(response[1]['body'], [])
