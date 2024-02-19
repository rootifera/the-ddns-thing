import os
import configparser

CONFIG_DIR = "config"
DOMAINS_CFG_FILE = os.path.join(CONFIG_DIR, "domains.cfg")
CREDENTIALS_CFG_FILE = os.path.join(CONFIG_DIR, "credentials.cfg")


def ensure_config_dir_exists():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)


def ensure_config_file_exists(file_path, default_contents):
    print(f"Checking file: {file_path}")
    if not os.path.isfile(file_path):
        with open(file_path, 'w') as file:
            file.write(default_contents)


def check_and_create_config_files():
    ensure_config_dir_exists()

    # Formatting notes
    default_domains_content = ("# Add your domains here\n"
                               "# Format:\n"
                               "#\n"
                               "# [app.domain.com]\n"
                               "# proxied=false\n")
    ensure_config_file_exists(DOMAINS_CFG_FILE, default_domains_content)

    default_credentials_content = ("# Add your credentials here. Format: \n"
                                   "# api_key=YOUR_API_KEY\n"
                                   "# zone_id=YOUR_ZONE_ID\n"
                                   "# email=YOUR_CLOUDFLARE_EMAIL\n"
                                   "api_key=\n"
                                   "zone_id=\n"
                                   "email=\n")
    ensure_config_file_exists(CREDENTIALS_CFG_FILE, default_credentials_content)


def read_config_file(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config


def get_domains_config():
    return read_config_file(DOMAINS_CFG_FILE)


def get_credentials_config():
    return read_config_file(CREDENTIALS_CFG_FILE)
