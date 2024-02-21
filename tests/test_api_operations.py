# tests/test_api_operations.py
import pytest

from the_ddns_thing import api_operations


def test_list_dns_records_success(requests_mock):
    api_key = "test_api_key"
    zone_id = "test_zone_id"
    email = "test@example.com"
    mock_response = {
        "result": [{"id": "123", "name": "example.com", "type": "A", "content": "192.0.2.1"}],
        "success": True
    }
    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                      json=mock_response, status_code=200)

    response = api_operations.list_dns_records(api_key, zone_id, email)
    assert response == mock_response


def test_list_dns_records_failure(requests_mock):
    api_key = "test_api_key"
    zone_id = "test_zone_id"
    email = "test@example.com"
    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                      status_code=500)

    with pytest.raises(Exception):
        api_operations.list_dns_records(api_key, zone_id, email)
