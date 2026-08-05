import pytest

from the_ddns_thing import api_operations


CREDENTIALS = {
    "cloudflare_email": "test@example.com",
    "cloudflare_api_key": "test-key",
}
ZONE_ID = "test-zone"


def test_list_dns_records_collects_all_pages(requests_mock):
    base_url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    requests_mock.get(
        f"{base_url}?type=A&per_page=100&page=1",
        json={
            "success": True,
            "result": [{"id": "1", "name": "first.example.com"}],
            "result_info": {"page": 1, "total_pages": 2},
        },
    )
    requests_mock.get(
        f"{base_url}?type=A&per_page=100&page=2",
        json={
            "success": True,
            "result": [{"id": "2", "name": "second.example.com"}],
            "result_info": {"page": 2, "total_pages": 2},
        },
    )

    payload = api_operations.list_dns_records(CREDENTIALS, ZONE_ID)

    assert [record["id"] for record in payload["result"]] == ["1", "2"]
    assert len(requests_mock.request_history) == 2


def test_list_dns_records_defaults_to_one_page_without_result_info(requests_mock):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?type=A&per_page=100&page=1"
    requests_mock.get(url, json={"success": True, "result": [{"id": "1"}]})

    payload = api_operations.list_dns_records(CREDENTIALS, ZONE_ID)

    assert payload["result"] == [{"id": "1"}]


@pytest.mark.parametrize("status_code", [401, 500])
def test_list_dns_records_reports_http_failure(requests_mock, status_code):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?type=A&per_page=100&page=1"
    requests_mock.get(url, status_code=status_code)

    with pytest.raises(ValueError, match="Could not reach Cloudflare"):
        api_operations.list_dns_records(CREDENTIALS, ZONE_ID)


def test_create_dns_record_uses_global_key_headers_and_payload(requests_mock):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    requests_mock.post(url, json={"success": True, "result": {"id": "record-1"}})

    api_operations.create_dns_record(CREDENTIALS, ZONE_ID, "home.example.com", "1.2.3.4", False)

    request = requests_mock.last_request
    assert request.headers["X-Auth-Email"] == CREDENTIALS["cloudflare_email"]
    assert request.headers["X-Auth-Key"] == CREDENTIALS["cloudflare_api_key"]
    assert request.json() == {
        "type": "A",
        "name": "home.example.com",
        "content": "1.2.3.4",
        "proxied": False,
        "ttl": 1,
        "comment": "Created by the-ddns-thing",
    }


def test_update_dns_record_uses_put(requests_mock):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/record-1"
    requests_mock.put(url, json={"success": True, "result": {"id": "record-1"}})

    api_operations.update_record_by_id(
        CREDENTIALS, ZONE_ID, "record-1", "home.example.com", "4.3.2.1", True
    )

    assert requests_mock.last_request.method == "PUT"
    assert requests_mock.last_request.json()["content"] == "4.3.2.1"


def test_api_error_message_is_exposed(requests_mock):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    requests_mock.post(
        url,
        json={"success": False, "errors": [{"message": "Record already exists"}]},
        status_code=400,
    )

    with pytest.raises(ValueError, match="Record already exists"):
        api_operations.create_dns_record(CREDENTIALS, ZONE_ID, "home.example.com", "1.2.3.4", False)


@pytest.mark.parametrize(
    "error",
    [
        {"code": 6003, "message": "Invalid request headers"},
        {"code": 6111, "message": "Invalid format for Authorization header"},
    ],
)
def test_authentication_errors_explain_required_credentials(requests_mock, error):
    url = "https://api.cloudflare.com/client/v4/zones?per_page=1"
    requests_mock.get(url, json={"success": False, "errors": [error]}, status_code=400)

    with pytest.raises(ValueError, match="Global API Key; API Tokens are not supported"):
        api_operations.verify_credentials(CREDENTIALS)


def test_locally_invalid_header_explains_required_credentials(mocker):
    mocker.patch.object(
        api_operations.requests,
        "request",
        side_effect=api_operations.requests.exceptions.InvalidHeader("bad header"),
    )

    with pytest.raises(ValueError, match="Global API Key; API Tokens are not supported"):
        api_operations.verify_credentials(CREDENTIALS)
