from urllib.parse import quote

import requests

REQUEST_TIMEOUT_SECONDS = 10
AUTHENTICATION_HELP = (
    "Cloudflare rejected the credentials. Enter your Cloudflare account email and "
    "Global API Key; API Tokens are not supported by this setup form."
)


def _headers(credentials):
    return {
        "Content-Type": "application/json",
        "X-Auth-Email": credentials["cloudflare_email"],
        "X-Auth-Key": credentials["cloudflare_api_key"],
    }


def _error_message(payload):
    errors = payload.get("errors", [])
    messages = [error.get("message", "Unknown Cloudflare error") for error in errors]
    error_codes = {error.get("code") for error in errors}

    if error_codes.intersection({6003, 6111}) or any(
        "invalid request headers" in message.lower() for message in messages
    ):
        return AUTHENTICATION_HELP

    return ", ".join(messages)


def _request(method, url, credentials, **kwargs):
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(credentials),
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )
        payload = response.json()
    except requests.exceptions.InvalidHeader as exc:
        raise ValueError(AUTHENTICATION_HELP) from exc
    except requests.RequestException as exc:
        raise ValueError(f"Could not reach Cloudflare: {exc}") from exc
    except ValueError as exc:
        raise ValueError("Cloudflare returned an invalid response.") from exc

    if not response.ok or not payload.get("success", False):
        message = _error_message(payload)
        if message:
            raise ValueError(message)
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"Could not reach Cloudflare: {exc}") from exc
        raise ValueError("Cloudflare API request failed.")

    return payload


def resolve_zone_id(credentials, root_domain):
    encoded_name = quote(root_domain, safe="")
    url = f"https://api.cloudflare.com/client/v4/zones?name={encoded_name}&status=active"
    payload = _request("GET", url, credentials)
    results = payload.get("result", [])

    if not results:
        raise ValueError(
            f"No active Cloudflare zone found for {root_domain}. "
            "Check the domain, email, and API key."
        )

    return results[0]["id"]


def verify_credentials(credentials):
    url = "https://api.cloudflare.com/client/v4/zones?per_page=1"
    _request("GET", url, credentials)
    return True


def list_zones(credentials):
    page = 1
    zones = []

    while True:
        url = f"https://api.cloudflare.com/client/v4/zones?status=active&per_page=50&page={page}"
        payload = _request("GET", url, credentials)
        zones.extend(payload.get("result", []))

        result_info = payload.get("result_info", {})
        total_pages = result_info.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return zones


def list_dns_records(credentials, zone_id):
    page = 1
    records = []
    last_payload = None

    while True:
        url = (
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
            f"?type=A&per_page=100&page={page}"
        )
        last_payload = _request("GET", url, credentials)
        records.extend(last_payload.get("result", []))

        result_info = last_payload.get("result_info", {})
        total_pages = result_info.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    # Keep the existing response shape so callers can consume the aggregated
    # records in exactly the same way as a single Cloudflare response.
    payload = dict(last_payload or {})
    payload["result"] = records
    return payload


def create_dns_record(credentials, zone_id, name, ip_address, proxied):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    data = {
        "type": "A",
        "name": name,
        "content": ip_address,
        "proxied": proxied,
        "ttl": 1,
        "comment": "Created by the-ddns-thing",
    }
    return _request("POST", url, credentials, json=data)


def update_record_by_id(credentials, zone_id, record_id, name, new_ip, proxied):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    data = {
        "type": "A",
        "name": name,
        "content": new_ip,
        "proxied": proxied,
        "ttl": 1,
    }
    return _request("PUT", url, credentials, json=data)


def delete_record_by_id(credentials, zone_id, record_id):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    return _request("DELETE", url, credentials)
