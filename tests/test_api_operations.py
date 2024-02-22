# tests/test_api_operations.py
import pytest

from the_ddns_thing import api_operations

API_TOKEN = 'test_token'
ZONE_ID = 'test_zone'
EMAIL = 'test@email.com'
RECORD_NAME = 'test.example.com'
RECORD_ID = '123'
CURRENT_IP = '1.2.3.4'
NEW_IP = '4.3.2.1'
PROXIED = False


def test_list_dns_records_success(requests_mock):
    mock_response = {
        "result": [{"id": RECORD_ID, "name": "example.com", "type": "A", "content": CURRENT_IP}],
        "success": True
    }
    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records",
                      json=mock_response, status_code=200)

    response = api_operations.list_dns_records(API_TOKEN, ZONE_ID, EMAIL)
    assert response == mock_response


def test_list_dns_records_failure(requests_mock):
    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records",
                      status_code=500)

    with pytest.raises(Exception):
        api_operations.list_dns_records(API_TOKEN, ZONE_ID, EMAIL)


def test_create_dns_record_success(requests_mock):
    mock_response = {
        "result": {"id": "123", "name": RECORD_NAME, "type": "A", "content": CURRENT_IP},
        "success": True
    }

    requests_mock.post(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records",
                       json=mock_response, status_code=200)

    response = api_operations.create_dns_record(API_TOKEN, ZONE_ID, EMAIL, RECORD_NAME, CURRENT_IP, PROXIED)
    assert response == mock_response


def test_create_dns_record_failure(requests_mock):
    requests_mock.post(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records",
                       status_code=500)

    with pytest.raises(Exception):
        api_operations.create_dns_record(API_TOKEN, ZONE_ID, EMAIL, RECORD_NAME, CURRENT_IP, PROXIED)


def test_check_ip_changes_by_id_changed(requests_mock):
    mock_response = {"result": {"id": RECORD_ID, "content": NEW_IP}}

    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}",
                      json=mock_response, status_code=200)

    result = api_operations.check_ip_changes_by_id(API_TOKEN, ZONE_ID, EMAIL, RECORD_ID, CURRENT_IP)
    assert result is True


def test_check_ip_changes_by_id_unchanged(requests_mock):
    mock_response = {"result": {"id": RECORD_ID, "content": CURRENT_IP}}

    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}",
                      json=mock_response, status_code=200)

    result = api_operations.check_ip_changes_by_id(API_TOKEN, ZONE_ID, EMAIL, RECORD_ID, CURRENT_IP)
    assert result is False


def test_check_ip_changes_by_id_failure(requests_mock):
    requests_mock.get(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}",
                      status_code=500)

    with pytest.raises(Exception):
        api_operations.check_ip_changes_by_id(API_TOKEN, ZONE_ID, EMAIL, RECORD_ID, CURRENT_IP)


def test_update_record_by_id_success(requests_mock):
    mock_response = {
        "result": {"id": RECORD_ID, "content": NEW_IP, "proxied": PROXIED},
        "success": True
    }

    requests_mock.patch(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}",
                        json=mock_response, status_code=200)

    response = api_operations.update_record_by_id(API_TOKEN, ZONE_ID, EMAIL, RECORD_ID, NEW_IP, PROXIED)
    assert response == mock_response


def test_update_record_by_id_failure(requests_mock):
    requests_mock.patch(f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}",
                        status_code=500)

    with pytest.raises(Exception):
        api_operations.update_record_by_id(API_TOKEN, ZONE_ID, EMAIL, RECORD_ID, NEW_IP, PROXIED)


def test_verify_api_key_success(requests_mock):
    mock_response = {
        "success": True,
        "result": {"status": "active"}
    }

    requests_mock.get("https://api.cloudflare.com/client/v4/user/tokens/verify",
                      json=mock_response, status_code=200)

    result = api_operations.verify_api_token(API_TOKEN)
    assert result is True


def test_verify_api_key_failure(requests_mock):
    mock_response = {"success": False}

    requests_mock.get("https://api.cloudflare.com/client/v4/user/tokens/verify",
                      json=mock_response, status_code=400)

    result = api_operations.verify_api_token(API_TOKEN)
    assert result is False
