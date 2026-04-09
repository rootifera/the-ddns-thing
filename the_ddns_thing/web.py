import secrets
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

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

    @app.before_request
    def load_current_user():
        user_id = session.get("user_id")
        g.current_user = db.get_admin_user(user_id) if user_id else None

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
        runtime = db.get_runtime_config()
        domains = db.list_domains()
        subdomains = db.list_subdomains()
        return render_template(
            "dashboard.html",
            runtime=runtime,
            domains=domains,
            subdomains=subdomains,
            sync_interval_seconds=app.config["SYNC_INTERVAL_SECONDS"],
        )

    @app.post("/domains")
    @login_required
    def add_domain():
        root_domain = request.form.get("root_domain", "")
        try:
            normalized = sync_service.normalize_root_domain(root_domain)
            credentials = {
                "cloudflare_email": db.get_runtime_config()["cloudflare_email"],
                "cloudflare_api_key": db.get_runtime_config()["cloudflare_api_key"],
            }
            zone_id = api_operations.resolve_zone_id(credentials, normalized)
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

        domain = db.get_domain(int(domain_id)) if domain_id.isdigit() else None
        if not domain:
            flash("Choose a valid domain first.", "error")
            return redirect(url_for("dashboard"))

        try:
            normalized = sync_service.normalize_subdomain(name, domain["root_domain"])
            db.add_subdomain(domain["id"], normalized, proxied)
            sync_result = sync_service.run_sync_cycle()
            flash(
                f"Added {normalized}.{domain['root_domain']}. {sync_result['summary']}",
                "success",
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc), "error")
        except Exception as exc:
            db.update_sync_status("error", "Sync failed after adding a subdomain.", str(exc))
            flash(f"Subdomain saved, but sync failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.post("/subdomains/<int:subdomain_id>/delete")
    @login_required
    def delete_subdomain(subdomain_id):
        subdomain = db.get_subdomain(subdomain_id)
        if not subdomain:
            flash("Subdomain not found.", "error")
            return redirect(url_for("dashboard"))

        try:
            sync_service.delete_managed_subdomain(subdomain)
            flash("Subdomain removed.", "success")
        except Exception as exc:
            flash(f"Could not remove subdomain: {exc}", "error")

        return redirect(url_for("dashboard"))

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

    return app
