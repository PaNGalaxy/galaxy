import pytest
import requests
import responses

from galaxy.util import url_get


@responses.activate
def test_get_url_ok():
    url = "https://toolshed.g2.bx.psu.edu/"
    responses.add(responses.GET, url, body="OK", status=200)
    text = url_get(url)
    assert text == "OK"


@responses.activate
def test_get_url_forbidden():
    url = "https://toolshed.g2.bx.psu.edu/"
    responses.add(responses.GET, url, body="Forbidden", status=403)
    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        url_get(url)
    assert "403 Client Error: Forbidden for url: https://toolshed.g2.bx.psu.edu/" in str(excinfo)


