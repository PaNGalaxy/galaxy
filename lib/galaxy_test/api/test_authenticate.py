import base64

from requests import get

from ._framework import ApiTestCase

TEST_USER_EMAIL = "auth_user_test@bx.psu.edu"
TEST_USER_PASSWORD = "testpassword1"


class AuthenticationApiTestCase(ApiTestCase):

    def test_auth(self):
        self._setup_user(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        baseauth_url = self._api_url("authenticate/baseauth", use_key=False)
        unencoded_credentials = f"{TEST_USER_EMAIL}:{TEST_USER_PASSWORD}"
        authorization = base64.b64encode(unencoded_credentials.encode("utf-8"))
        headers = {
            "Authorization": authorization,
        }
        auth_response = get(baseauth_url, headers=headers)
        self._assert_status_code_is(auth_response, 200)
        auth_dict = auth_response.json()
        self._assert_has_keys(auth_dict, "api_key")

        # Verify key...
        random_api_url = self._api_url("users", use_key=False)
        random_api_response = get(random_api_url, params=dict(key=auth_dict["api_key"]))
        self._assert_status_code_is(random_api_response, 200)
