import os
from contextlib import contextmanager
from urllib.parse import (
    urlencode,
    urljoin,
)

import requests

from .api_asserts import (
    assert_error_code_is,
    assert_has_keys,
    assert_not_has_keys,
    assert_status_code_is,
    assert_status_code_is_ok,
)
from .api_util import (
    ADMIN_TEST_USER,
    get_admin_api_key,
    get_user_api_key,
    OTHER_USER,
    TEST_USER,
)
from .interactor import TestCaseGalaxyInteractor as BaseInteractor


class UsesApiTestCaseMixin:
    url: str

    def tearDown(self):
        if os.environ.get('GALAXY_TEST_EXTERNAL') is None:
            # Only kill running jobs after test for managed test instances
            for job in self.galaxy_interactor.get('jobs?state=running&?user_details=true').json():
                self._delete(f"jobs/{job['id']}")

    def _api_url(self, path, params=None, use_key=None, use_admin_key=None):
        if not params:
            params = {}
        url = urljoin(self.url, f"api/{path}")
        if use_key:
            params["key"] = self.galaxy_interactor.api_key
        if use_admin_key:
            params["key"] = self.galaxy_interactor.master_api_key
        query = urlencode(params)
        if query:
            url = f"{url}?{query}"
        return url

    def _setup_interactor(self):
        self.user_api_key = get_user_api_key()
        self.master_api_key = get_admin_api_key()
        self.galaxy_interactor = self._get_interactor()

    def _get_interactor(self, api_key=None):
        return ApiTestInteractor(self, api_key=api_key)

    def _setup_user(self, email, password=None, is_admin=True):
        self.galaxy_interactor.ensure_user_with_email(email, password=password)
        users = self._get("users", admin=is_admin).json()
        user = [user for user in users if user["email"] == email][0]
        return user

    def _setup_user_get_key(self, email, password=None, is_admin=True):
        user = self._setup_user(email, password, is_admin)
        return user, self._post(f"users/{user['id']}/api_key", admin=True).json()

    @contextmanager
    def _different_user(self, email=OTHER_USER, anon=False):
        """ Use in test cases to switch get/post operations to act as new user

        ..code-block:: python

            with self._different_user("other_user@bx.psu.edu"):
                self._get("histories")  # Gets other_user@bx.psu.edu histories.

        """
        original_api_key = self.user_api_key
        original_interactor_key = self.galaxy_interactor.api_key
        original_cookies = self.galaxy_interactor.cookies
        if anon:
            cookies = requests.get(self.url).cookies
            self.galaxy_interactor.cookies = cookies
            new_key = None
        else:
            _, new_key = self._setup_user_get_key(email)
        try:
            self.user_api_key = new_key
            self.galaxy_interactor.api_key = new_key
            yield
        finally:
            self.user_api_key = original_api_key
            self.galaxy_interactor.api_key = original_interactor_key
            self.galaxy_interactor.cookies = original_cookies

    def _get(self, *args, **kwds):
        return self.galaxy_interactor.get(*args, **kwds)

    def _post(self, *args, **kwds):
        return self.galaxy_interactor.post(*args, **kwds)

    def _delete(self, *args, **kwds):
        return self.galaxy_interactor.delete(*args, **kwds)

    def _put(self, *args, **kwds):
        return self.galaxy_interactor.put(*args, **kwds)

    def _patch(self, *args, **kwds):
        return self.galaxy_interactor.patch(*args, **kwds)

    def _assert_status_code_is_ok(self, response):
        assert_status_code_is_ok(response)

    def _assert_status_code_is(self, response, expected_status_code):
        assert_status_code_is(response, expected_status_code)

    def _assert_has_keys(self, response, *keys):
        assert_has_keys(response, *keys)

    def _assert_not_has_keys(self, response, *keys):
        assert_not_has_keys(response, *keys)

    def _assert_error_code_is(self, response, error_code):
        assert_error_code_is(response, error_code)

    def _random_key(self):  # Used for invalid request testing...
        return "1234567890123456"

    _assert_has_key = _assert_has_keys


class ApiTestInteractor(BaseInteractor):
    """ Specialized variant of the API interactor (originally developed for
    tool functional tests) for testing the API generally.
    """

    def __init__(self, test_case, api_key=None):
        self.cookies = None
        admin = getattr(test_case, "require_admin_user", False)
        test_user = TEST_USER if not admin else ADMIN_TEST_USER
        super().__init__(test_case, test_user=test_user, api_key=api_key)

    # This variant the lower level get and post methods are meant to be used
    # directly to test API - instead of relying on higher-level constructs for
    # specific pieces of the API (the way it is done with the variant for tool)
    # testing.
    def get(self, *args, **kwds):
        return self._get(*args, **kwds)

    def post(self, *args, **kwds):
        return self._post(*args, **kwds)

    def delete(self, *args, **kwds):
        return self._delete(*args, **kwds)

    def patch(self, *args, **kwds):
        return self._patch(*args, **kwds)

    def put(self, *args, **kwds):
        return self._put(*args, **kwds)
