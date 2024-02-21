# tests/test_ip_fetcher.py
import pytest
import requests

from the_ddns_thing import ip_fetcher


@pytest.fixture
def mock_get_request(mocker):
    """ Fixture to mock requests.get """
    return mocker.patch('the_ddns_thing.ip_fetcher.requests.get')


def test_get_public_ip_from_url_success(mock_get_request):
    mock_get_request.return_value.status_code = 200
    mock_get_request.return_value.text = "1.2.3.4"

    ip = ip_fetcher.get_public_ip_from_url("http://dummyurl.com")
    assert ip == "1.2.3.4"


def test_get_public_ip_from_url_failure(mock_get_request):
    mock_get_request.side_effect = requests.RequestException

    ip = ip_fetcher.get_public_ip_from_url("http://dummyurl.com")
    assert ip is None


@pytest.fixture
def mock_get_public_ip_from_url(mocker):
    """ Fixture to mock get_public_ip_from_url """
    return mocker.patch('the_ddns_thing.ip_fetcher.get_public_ip_from_url')


def test_get_public_ip(mock_get_public_ip_from_url):
    mock_get_public_ip_from_url.side_effect = [None, "1.2.3.4", None]

    ip = ip_fetcher.get_public_ip()
    assert ip == "1.2.3.4"


def test_get_public_ip_all_fail(mock_get_public_ip_from_url):
    mock_get_public_ip_from_url.return_value = None

    with pytest.raises(Exception) as excinfo:
        ip_fetcher.get_public_ip()
    assert "Getting public IP failed" in str(excinfo.value)
