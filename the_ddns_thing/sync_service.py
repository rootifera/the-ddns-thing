import logging
import re
import threading
from time import sleep

from . import api_operations, db, ip_fetcher

LOGGER = logging.getLogger(__name__)
SUBDOMAIN_PATTERN = re.compile(r"^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)*$")


def normalize_subdomain(value, root_domain=None):
    normalized = value.strip().lower().rstrip(".")
    if not normalized:
        raise ValueError("Subdomain is required.")

    if root_domain and normalized == root_domain:
        return "@"

    if root_domain and normalized.endswith(f".{root_domain}"):
        normalized = normalized[: -(len(root_domain) + 1)]
        if not normalized:
            return "@"

    if normalized == "@":
        return "@"

    if not SUBDOMAIN_PATTERN.fullmatch(normalized):
        raise ValueError("Subdomains may only contain letters, numbers, hyphens, and dots.")

    return normalized


def normalize_root_domain(value):
    normalized = value.strip().lower().rstrip(".")
    if not normalized:
        raise ValueError("Root domain is required.")
    if not SUBDOMAIN_PATTERN.fullmatch(normalized) or "." not in normalized:
        raise ValueError("Enter a valid root domain like example.com.")
    return normalized


def full_hostname(subdomain_name, root_domain):
    if subdomain_name == "@":
        return root_domain
    return f"{subdomain_name}.{root_domain}"


def _credentials():
    runtime = db.get_runtime_config()
    return {
        "cloudflare_email": runtime["cloudflare_email"],
        "cloudflare_api_key": runtime["cloudflare_api_key"],
    }


def delete_managed_subdomain(subdomain):
    if subdomain.get("record_id"):
        api_operations.delete_record_by_id(_credentials(), subdomain["zone_id"], subdomain["record_id"])
    db.delete_subdomain(subdomain["id"])


def run_sync_cycle():
    if not db.is_setup_complete():
        return {"status": "idle", "summary": "Waiting for setup to complete."}

    public_ip = ip_fetcher.get_public_ip()
    credentials = _credentials()
    domains = db.list_domains()
    subdomains = db.list_subdomains()
    subdomains_by_domain = {}

    for subdomain in subdomains:
        subdomains_by_domain.setdefault(subdomain["domain_id"], []).append(subdomain)

    created = 0
    updated = 0
    unchanged = 0
    adopted = 0

    for domain in domains:
        domain_subdomains = subdomains_by_domain.get(domain["id"], [])
        if not domain_subdomains:
            continue

        dns_records = api_operations.list_dns_records(credentials, domain["zone_id"]).get("result", [])
        existing_by_name = {record["name"].lower(): record for record in dns_records if record.get("name")}
        existing_by_id = {record["id"]: record for record in dns_records if record.get("id")}

        for subdomain in domain_subdomains:
            fqdn = full_hostname(subdomain["name"], domain["root_domain"])
            record = None

            if subdomain.get("record_id"):
                record = existing_by_id.get(subdomain["record_id"])

            if record is None:
                record = existing_by_name.get(fqdn.lower())

            if record is None:
                payload = api_operations.create_dns_record(
                    credentials,
                    domain["zone_id"],
                    fqdn,
                    public_ip,
                    bool(subdomain["proxied"]),
                )
                db.update_subdomain_record(subdomain["id"], payload["result"]["id"])
                db.record_subdomain_ip(subdomain["id"], public_ip)
                created += 1
                continue

            if record.get("id") != subdomain.get("record_id"):
                db.update_subdomain_record(subdomain["id"], record["id"])
                adopted += 1

            if record.get("content") != public_ip or bool(record.get("proxied")) != bool(subdomain["proxied"]):
                api_operations.update_record_by_id(
                    credentials,
                    domain["zone_id"],
                    record["id"],
                    fqdn,
                    public_ip,
                    bool(subdomain["proxied"]),
                )
                db.record_subdomain_ip(subdomain["id"], public_ip, record.get("content"))
                updated += 1
            else:
                db.record_subdomain_ip(subdomain["id"], public_ip)
                unchanged += 1

    summary = (
        f"Public IP {public_ip}. "
        f"Domains {len(domains)}, created {created}, updated {updated}, unchanged {unchanged}, adopted {adopted}."
    )
    db.update_sync_status("ok", summary, "", public_ip)
    return {"status": "ok", "summary": summary}


class SyncWorker:
    def __init__(self, app, interval_seconds):
        self.app = app
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True, name="ddns-sync-worker")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    run_sync_cycle()
            except Exception as exc:
                LOGGER.exception("Background sync failed")
                db.update_sync_status("error", "Background sync failed.", str(exc))

            sleep(db.get_sync_interval_seconds(self.interval_seconds))
