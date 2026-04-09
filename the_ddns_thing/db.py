import os
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
            ],
        )
        connection.execute(
            """
            INSERT INTO admin_users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (admin_username, generate_password_hash(admin_password), utc_now()),
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
    return [dict(row) for row in rows]


def get_subdomain(subdomain_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                subdomains.id,
                subdomains.domain_id,
                subdomains.name,
                subdomains.record_id,
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
    return dict(row) if row else None


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


def update_sync_status(status, summary, error_message="", public_ip=None):
    set_setting("last_sync_status", status)
    set_setting("last_sync_summary", summary)
    set_setting("last_sync_error", error_message)
    set_setting("last_sync_at", utc_now())
    if public_ip is not None:
        set_setting("last_public_ip", public_ip)


def get_runtime_config():
    return get_settings(
        [
            "cloudflare_email",
            "cloudflare_api_key",
            "last_sync_status",
            "last_sync_summary",
            "last_sync_error",
            "last_public_ip",
            "last_sync_at",
        ]
    )
