import requests


def list_dns_records(api_key, zone_id, email):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Auth-Email": email
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


def create_dns_record(api_key, zone_id, email, name, ip_address, proxied):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Auth-Email": email
    }
    data = {
        "type": "A",
        "name": name,
        "content": ip_address,
        "proxied": proxied,
        "ttl": 600,  # Change if you need
        "comment": "Created by cloudflare-ddns-thing"  # Change that too
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


def check_ip_changes_by_id(api_key, zone_id, email, record_id, current_ip):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Auth-Email": email
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        record_data = response.json()['result']
        return record_data['content'] != current_ip
    else:
        response.raise_for_status()


def update_record_by_id(api_key, zone_id, email, record_id, new_ip, proxied):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Auth-Email": email
    }
    data = {
        "content": new_ip,
        "proxied": proxied
    }

    response = requests.patch(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()
