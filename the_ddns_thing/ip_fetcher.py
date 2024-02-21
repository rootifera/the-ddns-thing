import re

import requests


def get_public_ip_from_url(url):
    try:
        response = requests.get(url)
        ip = response.text.strip()
        if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", ip):
            return ip
    except requests.RequestException:
        pass
    return None


def get_public_ip():
    urls = [
        "http://checkip.amazonaws.com/",
        "http://icanhazip.com/",
        "http://ident.me/",
    ]

    for url in urls:
        ip = get_public_ip_from_url(url)
        if ip is not None:
            return ip

    raise Exception("Getting public IP failed, check your internet connection.")
