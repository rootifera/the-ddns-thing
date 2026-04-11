import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_DATA_DIR = os.getcwd()


def get_data_dir():
    return os.environ.get("THE_DDNS_THING_DATA_DIR", DEFAULT_DATA_DIR)


def get_database_file():
    return os.path.join(get_data_dir(), "the-ddns-thing.db")


def get_secret_key_file():
    return os.path.join(get_data_dir(), "secret.key")


def ensure_app_root():
    os.makedirs(get_data_dir(), exist_ok=True)


def get_database_path():
    ensure_app_root()
    return get_database_file()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _table_columns(connection, table_name):
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _table_sql(connection, table_name):
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row["sql"] if row and row["sql"] else ""


def _rebuild_subdomains_table(connection):
    connection.execute("DROP INDEX IF EXISTS idx_subdomains_domain_name")
    connection.execute(
        """
        CREATE TABLE subdomains_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id INTEGER,
            name TEXT NOT NULL,
            record_id TEXT,
            proxied INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO subdomains_new (id, domain_id, name, record_id, proxied, created_at, updated_at)
        SELECT id, domain_id, name, record_id, proxied, created_at, updated_at
        FROM subdomains
        """
    )
    connection.execute("DROP TABLE subdomains")
    connection.execute("ALTER TABLE subdomains_new RENAME TO subdomains")


def _migrate_schema(connection):
    domain_columns = _table_columns(connection, "managed_domains")
    if not domain_columns:
        connection.execute(
            """
            CREATE TABLE managed_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_domain TEXT NOT NULL UNIQUE,
                zone_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    subdomain_columns = _table_columns(connection, "subdomains")
    if "domain_id" not in subdomain_columns:
        connection.execute("ALTER TABLE subdomains ADD COLUMN domain_id INTEGER")
    if "current_ip" not in subdomain_columns:
        connection.execute("ALTER TABLE subdomains ADD COLUMN current_ip TEXT")
    if "last_ip" not in subdomain_columns:
        connection.execute("ALTER TABLE subdomains ADD COLUMN last_ip TEXT")

    ip_history_columns = _table_columns(connection, "subdomain_ip_history")
    if not ip_history_columns:
        connection.execute(
            """
            CREATE TABLE subdomain_ip_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subdomain_id INTEGER NOT NULL,
                ip_address TEXT NOT NULL,
                observed_at TEXT NOT NULL
            )
            """
        )

    subdomains_sql = _table_sql(connection, "subdomains").lower()
    if "name text not null unique" in subdomains_sql or "unique(name)" in subdomains_sql:
        _rebuild_subdomains_table(connection)

    if "root_domain" in _table_columns(connection, "settings"):
        legacy_root_domain = connection.execute(
            "SELECT value FROM settings WHERE key = 'root_domain'"
        ).fetchone()
        legacy_zone_id = connection.execute(
            "SELECT value FROM settings WHERE key = 'zone_id'"
        ).fetchone()
        if legacy_root_domain and legacy_zone_id:
            timestamp = utc_now()
            connection.execute(
                """
                INSERT OR IGNORE INTO managed_domains (root_domain, zone_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (legacy_root_domain["value"], legacy_zone_id["value"], timestamp, timestamp),
            )
            domain_row = connection.execute(
                "SELECT id FROM managed_domains WHERE root_domain = ?",
                (legacy_root_domain["value"],),
            ).fetchone()
            if domain_row:
                connection.execute(
                    "UPDATE subdomains SET domain_id = ? WHERE domain_id IS NULL",
                    (domain_row["id"],),
                )

    connection.execute("DELETE FROM settings WHERE key IN ('root_domain', 'zone_id')")
    connection.execute(
        """
        DELETE FROM subdomains
        WHERE domain_id IS NULL
        """
    )


def init_db():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subdomains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER,
                name TEXT NOT NULL,
                record_id TEXT,
                proxied INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _migrate_schema(connection)
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_subdomains_domain_name
            ON subdomains(domain_id, name)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subdomain_ip_history_subdomain
            ON subdomain_ip_history(subdomain_id, observed_at DESC)
            """
        )


def load_secret_key():
    ensure_app_root()
    secret_key_file = get_secret_key_file()
    if os.path.isfile(secret_key_file):
        with open(secret_key_file, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    return None


def save_secret_key(secret_key):
    ensure_app_root()
    with open(get_secret_key_file(), "w", encoding="utf-8") as handle:
        handle.write(secret_key)


def get_setting(key, default=None):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def get_settings(keys):
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join(['?'] * len(keys))})",
            tuple(keys),
        ).fetchall()
    values = {row["key"]: row["value"] for row in rows}
    return {key: values.get(key) for key in keys}


def is_setup_complete():
    required_keys = ["cloudflare_email", "cloudflare_api_key"]
    values = get_settings(required_keys)
    if not all(values.values()):
        return False

    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM admin_users").fetchone()
    return bool(row["count"])


def verify_admin_user(username, password):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash
            FROM admin_users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return None

    return {"id": row["id"], "username": row["username"]}


def get_admin_user(user_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username FROM admin_users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if not row:
        return None

    return {"id": row["id"], "username": row["username"]}


def bootstrap_application(*, cloudflare_email, cloudflare_api_key, admin_username, admin_password):
    created_at = utc_now()
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            [
                ("cloudflare_email", cloudflare_email),
                ("cloudflare_api_key", cloudflare_api_key),
                ("last_sync_status", "never"),
                ("last_sync_summary", "No sync has run yet."),
                ("last_sync_error", ""),
                ("last_public_ip", ""),
                ("last_sync_at", ""),
                ("sync_interval_seconds", "300"),
                ("app_created_at", created_at),
                ("sync_runs_total", "0"),
                ("sync_runs_successful", "0"),
                ("sync_runs_failed", "0"),
            ],
        )
        connection.execute(
            """
            INSERT INTO admin_users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (admin_username, generate_password_hash(admin_password), created_at),
        )


def list_domains():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, root_domain, zone_id, created_at, updated_at
            FROM managed_domains
            ORDER BY root_domain ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_domain(domain_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, root_domain, zone_id, created_at, updated_at
            FROM managed_domains
            WHERE id = ?
            """,
            (domain_id,),
        ).fetchone()
    return dict(row) if row else None


def add_domain(root_domain, zone_id):
    timestamp = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO managed_domains (root_domain, zone_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (root_domain, zone_id, timestamp, timestamp),
        )
    return cursor.lastrowid


def get_domain_by_root_domain(root_domain):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, root_domain, zone_id, created_at, updated_at
            FROM managed_domains
            WHERE root_domain = ?
            """,
            (root_domain,),
        ).fetchone()
    return dict(row) if row else None


def delete_domain(domain_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM managed_domains WHERE id = ?", (domain_id,))


def domain_has_subdomains(domain_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM subdomains WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
    return bool(row["count"])


def list_subdomains():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                subdomains.id,
                subdomains.domain_id,
                subdomains.name,
                subdomains.record_id,
                subdomains.current_ip,
                subdomains.last_ip,
                subdomains.proxied,
                subdomains.created_at,
                subdomains.updated_at,
                managed_domains.root_domain,
                managed_domains.zone_id
            FROM subdomains
            JOIN managed_domains ON managed_domains.id = subdomains.domain_id
            ORDER BY managed_domains.root_domain ASC, subdomains.name ASC
            """
        ).fetchall()

    subdomains = [dict(row) for row in rows]
    _attach_recent_ip_history(subdomains)
    return subdomains


def get_subdomain(subdomain_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                subdomains.id,
                subdomains.domain_id,
                subdomains.name,
                subdomains.record_id,
                subdomains.current_ip,
                subdomains.last_ip,
                subdomains.proxied,
                subdomains.created_at,
                subdomains.updated_at,
                managed_domains.root_domain,
                managed_domains.zone_id
            FROM subdomains
            JOIN managed_domains ON managed_domains.id = subdomains.domain_id
            WHERE subdomains.id = ?
            """,
            (subdomain_id,),
        ).fetchone()
    subdomain = dict(row) if row else None
    if subdomain:
        _attach_recent_ip_history([subdomain])
    return subdomain


def add_subdomain(domain_id, name, proxied):
    timestamp = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO subdomains (domain_id, name, record_id, proxied, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?, ?)
            """,
            (domain_id, name, int(bool(proxied)), timestamp, timestamp),
        )
    return cursor.lastrowid


def get_subdomain_by_domain_and_name(domain_id, name):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, domain_id, name, record_id, current_ip, last_ip, proxied, created_at, updated_at
            FROM subdomains
            WHERE domain_id = ? AND name = ?
            """,
            (domain_id, name),
        ).fetchone()
    return dict(row) if row else None


def delete_subdomain(subdomain_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM subdomains WHERE id = ?", (subdomain_id,))


def update_subdomain_record(subdomain_id, record_id):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE subdomains
            SET record_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (record_id, utc_now(), subdomain_id),
        )


def update_subdomain_details(subdomain_id, *, proxied=None, record_id=None, current_ip=None, last_ip=None):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT proxied, record_id, current_ip, last_ip
            FROM subdomains
            WHERE id = ?
            """,
            (subdomain_id,),
        ).fetchone()
        if not row:
            return

        connection.execute(
            """
            UPDATE subdomains
            SET proxied = ?, record_id = ?, current_ip = ?, last_ip = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                int(bool(proxied)) if proxied is not None else row["proxied"],
                record_id if record_id is not None else row["record_id"],
                current_ip if current_ip is not None else row["current_ip"],
                last_ip if last_ip is not None else row["last_ip"],
                utc_now(),
                subdomain_id,
            ),
        )


def record_subdomain_ip(subdomain_id, current_ip, previous_ip=None):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT current_ip, last_ip FROM subdomains WHERE id = ?",
            (subdomain_id,),
        ).fetchone()

        existing_current_ip = row["current_ip"] if row else None
        existing_last_ip = row["last_ip"] if row else None

        new_last_ip = existing_last_ip
        if previous_ip and previous_ip != current_ip:
            new_last_ip = previous_ip
        elif existing_current_ip and existing_current_ip != current_ip:
            new_last_ip = existing_current_ip

        connection.execute(
            """
            UPDATE subdomains
            SET current_ip = ?, last_ip = ?, updated_at = ?
            WHERE id = ?
            """,
            (current_ip, new_last_ip, utc_now(), subdomain_id),
        )

        history_to_insert = []

        if previous_ip and previous_ip != current_ip:
            history_to_insert.append(previous_ip)
        elif existing_current_ip and existing_current_ip != current_ip:
            history_to_insert.append(existing_current_ip)

        if existing_current_ip != current_ip:
            history_to_insert.append(current_ip)

        seen = set()
        for ip_address in history_to_insert:
            if not ip_address or ip_address in seen:
                continue
            seen.add(ip_address)
            connection.execute(
                """
                INSERT INTO subdomain_ip_history (subdomain_id, ip_address, observed_at)
                VALUES (?, ?, ?)
                """,
                (subdomain_id, ip_address, utc_now()),
            )


def _attach_recent_ip_history(subdomains, limit=5):
    if not subdomains:
        return

    subdomain_ids = [subdomain["id"] for subdomain in subdomains]
    placeholders = ",".join(["?"] * len(subdomain_ids))

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT subdomain_id, ip_address, observed_at
            FROM subdomain_ip_history
            WHERE subdomain_id IN ({placeholders})
            ORDER BY observed_at DESC
            """,
            tuple(subdomain_ids),
        ).fetchall()

    history_map = {}
    for row in rows:
        history_map.setdefault(row["subdomain_id"], [])
        if len(history_map[row["subdomain_id"]]) < limit:
            history_map[row["subdomain_id"]].append(
                {
                    "ip_address": row["ip_address"],
                    "observed_at": row["observed_at"],
                }
            )

    for subdomain in subdomains:
        subdomain["recent_ips"] = history_map.get(subdomain["id"], [])


def export_records():
    domains = list_domains()
    subdomains = list_subdomains()

    export_data = {
        "version": 1,
        "exported_at": utc_now(),
        "domains": [
            {
                "root_domain": domain["root_domain"],
                "zone_id": domain["zone_id"],
            }
            for domain in domains
        ],
        "subdomains": [
            {
                "domain": subdomain["root_domain"],
                "name": subdomain["name"],
                "proxied": bool(subdomain["proxied"]),
                "record_id": subdomain["record_id"],
                "current_ip": subdomain["current_ip"],
                "last_ip": subdomain["last_ip"],
                "recent_ips": subdomain.get("recent_ips", []),
            }
            for subdomain in subdomains
        ],
    }
    return export_data


def import_records(payload):
    if not isinstance(payload, dict):
        raise ValueError("Import file must contain a JSON object.")

    domains = payload.get("domains")
    subdomains = payload.get("subdomains")

    if not isinstance(domains, list) or not isinstance(subdomains, list):
        raise ValueError("Import file must include 'domains' and 'subdomains' lists.")

    imported_domains = 0
    imported_subdomains = 0

    domain_map = {}
    for item in domains:
        if not isinstance(item, dict):
            continue
        root_domain = item.get("root_domain")
        zone_id = item.get("zone_id")
        if not root_domain or not zone_id:
            continue

        existing_domain = get_domain_by_root_domain(root_domain)
        if existing_domain:
            domain_map[root_domain] = existing_domain["id"]
            continue

        domain_map[root_domain] = add_domain(root_domain, zone_id)
        imported_domains += 1

    for item in subdomains:
        if not isinstance(item, dict):
            continue

        root_domain = item.get("domain")
        name = item.get("name")
        if not root_domain or not name:
            continue

        domain_id = domain_map.get(root_domain)
        if not domain_id:
            existing_domain = get_domain_by_root_domain(root_domain)
            domain_id = existing_domain["id"] if existing_domain else None
        if not domain_id:
            continue

        existing_subdomain = get_subdomain_by_domain_and_name(domain_id, name)
        if existing_subdomain:
            update_subdomain_details(
                existing_subdomain["id"],
                proxied=item.get("proxied"),
                record_id=item.get("record_id"),
                current_ip=item.get("current_ip"),
                last_ip=item.get("last_ip"),
            )
            subdomain_id = existing_subdomain["id"]
        else:
            subdomain_id = add_subdomain(domain_id, name, bool(item.get("proxied")))
            update_subdomain_details(
                subdomain_id,
                record_id=item.get("record_id"),
                current_ip=item.get("current_ip"),
                last_ip=item.get("last_ip"),
            )
            imported_subdomains += 1

        recent_ips = item.get("recent_ips", [])
        if isinstance(recent_ips, list):
            for ip_entry in reversed(recent_ips):
                if isinstance(ip_entry, dict) and ip_entry.get("ip_address"):
                    record_subdomain_ip(
                        subdomain_id,
                        ip_entry["ip_address"],
                    )

    return {
        "domains": imported_domains,
        "subdomains": imported_subdomains,
    }


def update_sync_status(status, summary, error_message="", public_ip=None):
    set_setting("last_sync_status", status)
    set_setting("last_sync_summary", summary)
    set_setting("last_sync_error", error_message)
    set_setting("last_sync_at", utc_now())
    increment_setting("sync_runs_total")
    if status == "ok":
        increment_setting("sync_runs_successful")
    elif status == "error":
        increment_setting("sync_runs_failed")
    if public_ip is not None:
        set_setting("last_public_ip", public_ip)


def increment_setting(key, amount=1):
    current_value = get_setting(key, "0")
    try:
        new_value = int(current_value) + amount
    except (TypeError, ValueError):
        new_value = amount
    set_setting(key, str(new_value))


def get_runtime_config():
    return get_settings(
        [
            "cloudflare_email",
            "cloudflare_api_key",
            "app_created_at",
            "sync_interval_seconds",
            "sync_runs_total",
            "sync_runs_successful",
            "sync_runs_failed",
            "last_sync_status",
            "last_sync_summary",
            "last_sync_error",
            "last_public_ip",
            "last_sync_at",
        ]
    )


def get_sync_interval_seconds(default=300):
    raw_value = get_setting("sync_interval_seconds")
    try:
        interval = int(raw_value) if raw_value is not None else default
    except (TypeError, ValueError):
        return default
    return max(30, interval)
