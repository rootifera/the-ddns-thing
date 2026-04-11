import secrets
import sqlite3
import json
from datetime import datetime
from functools import wraps

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for

from . import api_operations, db, sync_service


def create_app(sync_interval_seconds=300):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    db.init_db()

    secret_key = db.load_secret_key()
    if not secret_key:
        secret_key = secrets.token_hex(32)
        db.save_secret_key(secret_key)

    app.config["SECRET_KEY"] = secret_key
    app.config["SYNC_INTERVAL_SECONDS"] = sync_interval_seconds

    @app.template_filter("friendly_datetime")
    def friendly_datetime(value):
        if not value:
            return "Never"
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return value
        return timestamp.strftime("%d %b %Y, %H:%M:%S UTC")

    @app.template_filter("record_display_name")
    def record_display_name(subdomain_name):
        return "Root domain" if subdomain_name == "@" else subdomain_name

    @app.template_filter("display_ip")
    def display_ip(value):
        return value or "Unknown"

    @app.template_filter("integer_or_zero")
    def integer_or_zero(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @app.before_request
    def load_current_user():
        user_id = session.get("user_id")
        g.current_user = db.get_admin_user(user_id) if user_id else None
        g.active_nav = None

    @app.before_request
    def require_setup_and_authentication():
        allowed_endpoints = {"setup", "login", "static"}
        endpoint = request.endpoint or ""

        if endpoint == "static":
            return None

        if not db.is_setup_complete():
            if endpoint != "setup":
                return redirect(url_for("setup"))
            return None

        if endpoint == "setup":
            return redirect(url_for("dashboard"))

        if endpoint == "login":
            if g.current_user:
                return redirect(url_for("dashboard"))
            return None

        if endpoint in allowed_endpoints:
            return None

        if not g.current_user:
            return redirect(url_for("login"))

        return None

    def login_required(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not g.current_user:
                return redirect(url_for("login"))
            return view_func(*args, **kwargs)

        return wrapped_view

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if db.is_setup_complete():
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            admin_username = request.form.get("admin_username", "").strip()
            admin_password = request.form.get("admin_password", "").strip()
            cloudflare_email = request.form.get("cloudflare_email", "").strip()
            cloudflare_api_key = request.form.get("cloudflare_api_key", "").strip()

            if not all([admin_username, admin_password, cloudflare_email, cloudflare_api_key]):
                flash("Every field is required.", "error")
                return render_template("setup.html")

            credentials = {
                "cloudflare_email": cloudflare_email,
                "cloudflare_api_key": cloudflare_api_key,
            }

            try:
                api_operations.verify_credentials(credentials)
                db.bootstrap_application(
                    cloudflare_email=cloudflare_email,
                    cloudflare_api_key=cloudflare_api_key,
                    admin_username=admin_username,
                    admin_password=admin_password,
                )
                user = db.verify_admin_user(admin_username, admin_password)
                session["user_id"] = user["id"]
                flash("Setup complete. Add the domains you want to manage.", "success")
                return redirect(url_for("dashboard"))
            except (ValueError, sqlite3.IntegrityError) as exc:
                flash(str(exc), "error")

        return render_template("setup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            user = db.verify_admin_user(username, password)

            if user:
                session["user_id"] = user["id"]
                return redirect(url_for("dashboard"))

            flash("Invalid username or password.", "error")

        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        g.active_nav = "dashboard"
        runtime = db.get_runtime_config()
        domains = db.list_domains()
        subdomains = db.list_subdomains()
        available_domains = []
        domains_error = None

        try:
            credentials = {
                "cloudflare_email": runtime["cloudflare_email"],
                "cloudflare_api_key": runtime["cloudflare_api_key"],
            }
            managed_zone_ids = {domain["zone_id"] for domain in domains}
            available_domains = [
                {
                    "root_domain": zone["name"],
                    "zone_id": zone["id"],
                    "is_managed": zone["id"] in managed_zone_ids,
                }
                for zone in api_operations.list_zones(credentials)
                if zone.get("name") and zone.get("id")
            ]
            available_domains.sort(key=lambda item: item["root_domain"])
        except ValueError as exc:
            domains_error = str(exc)

        return render_template(
            "dashboard.html",
            runtime=runtime,
            domains=domains,
            available_domains=available_domains,
            domains_error=domains_error,
            subdomains=subdomains,
            sync_interval_seconds=db.get_sync_interval_seconds(app.config["SYNC_INTERVAL_SECONDS"]),
        )

    @app.get("/subdomains")
    @login_required
    def subdomains_page():
        g.active_nav = "subdomains"
        domains = db.list_domains()
        subdomains = db.list_subdomains()
        selected_domain_id = session.get("last_subdomain_domain_id")
        return render_template(
            "subdomains.html",
            domains=domains,
            subdomains=subdomains,
            selected_domain_id=selected_domain_id,
        )

    @app.post("/domains/enable")
    @login_required
    def add_domain():
        root_domain = request.form.get("root_domain", "")
        zone_id = request.form.get("zone_id", "").strip()
        try:
            normalized = sync_service.normalize_root_domain(root_domain)
            if not zone_id:
                raise ValueError("Missing zone ID for selected domain.")
            db.add_domain(normalized, zone_id)
            flash(f"Added domain {normalized}.", "success")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc), "error")

        return redirect(url_for("dashboard"))

    @app.post("/domains/<int:domain_id>/delete")
    @login_required
    def delete_domain(domain_id):
        domain = db.get_domain(domain_id)
        if not domain:
            flash("Domain not found.", "error")
            return redirect(url_for("dashboard"))

        if db.domain_has_subdomains(domain_id):
            flash("Remove the subdomains under this domain first.", "error")
            return redirect(url_for("dashboard"))

        db.delete_domain(domain_id)
        flash(f"Removed domain {domain['root_domain']}.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/subdomains")
    @login_required
    def add_subdomain():
        domain_id = request.form.get("domain_id", "").strip()
        name = request.form.get("name", "")
        proxied = request.form.get("proxied") == "on"
        session["last_subdomain_domain_id"] = domain_id

        domain = db.get_domain(int(domain_id)) if domain_id.isdigit() else None
        if not domain:
            flash("Choose a valid domain first.", "error")
            return redirect(url_for("subdomains_page"))

        try:
            normalized = sync_service.normalize_subdomain(name, domain["root_domain"])
            db.add_subdomain(domain["id"], normalized, proxied)
            sync_result = sync_service.run_sync_cycle()
            fqdn = sync_service.full_hostname(normalized, domain["root_domain"])
            flash(
                f"Added {fqdn}. {sync_result['summary']}",
                "success",
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc), "error")
        except Exception as exc:
            db.update_sync_status("error", "Sync failed after adding a subdomain.", str(exc))
            flash(f"Subdomain saved, but sync failed: {exc}", "error")

        return redirect(url_for("subdomains_page"))

    @app.post("/subdomains/<int:subdomain_id>/delete")
    @login_required
    def delete_subdomain(subdomain_id):
        subdomain = db.get_subdomain(subdomain_id)
        if not subdomain:
            flash("Subdomain not found.", "error")
            return redirect(url_for("subdomains_page"))

        try:
            sync_service.delete_managed_subdomain(subdomain)
            flash("Subdomain removed.", "success")
        except Exception as exc:
            flash(f"Could not remove subdomain: {exc}", "error")

        return redirect(url_for("subdomains_page"))

    @app.post("/sync-now")
    @login_required
    def sync_now():
        try:
            result = sync_service.run_sync_cycle()
            flash(result["summary"], "success")
        except Exception as exc:
            db.update_sync_status("error", "Manual sync failed.", str(exc))
            flash(f"Manual sync failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.post("/settings/sync-interval")
    @login_required
    def update_sync_interval():
        raw_value = request.form.get("sync_interval_seconds", "").strip()
        try:
            interval = int(raw_value)
            if interval < 30:
                raise ValueError("Sync interval must be at least 30 seconds.")
            db.set_setting("sync_interval_seconds", str(interval))
            flash(f"Sync interval updated to {interval} seconds.", "success")
        except ValueError as exc:
            flash(str(exc), "error")

        return redirect(url_for("dashboard"))

    @app.get("/records/export")
    @login_required
    def export_records():
        payload = db.export_records()
        export_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=the-ddns-thing-records-{export_timestamp}.json"
            },
        )

    @app.post("/records/import")
    @login_required
    def import_records():
        upload = request.files.get("records_file")
        if not upload or not upload.filename:
            flash("Choose a JSON export file to import.", "error")
            return redirect(url_for("dashboard"))

        try:
            payload = json.load(upload.stream)
            result = db.import_records(payload)
            flash(
                f"Import complete. Added {result['domains']} domains and {result['subdomains']} subdomains.",
                "success",
            )
        except (ValueError, json.JSONDecodeError) as exc:
            flash(f"Import failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    return app
