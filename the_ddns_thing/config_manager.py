import configparser
import os
from . import utils

CONFIG_DIR = "config"
DOMAINS_CFG_FILE = os.path.join(CONFIG_DIR, "dns_records.cfg")
CREDENTIALS_CFG_FILE = os.path.join(CONFIG_DIR, "credentials.cfg")


def ensure_config_dir_exists():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)


def ensure_config_file_exists(file_path, default_contents):
    utils.print_cyan(f"Checking file: {file_path}")
    if not os.path.isfile(file_path):
        with open(file_path, 'w') as file:
            file.write(default_contents)
        return True
    return False


def check_and_create_config_files():
    ensure_config_dir_exists()
    is_first_run = False

    default_domains_content = ("# Add your dns records here\n"
                               "# Format:\n"
                               "#\n"
                               "# [app.domain.com]\n"
                               "# proxied=false\n"
                               "# id=Leave it blank")
    if ensure_config_file_exists(DOMAINS_CFG_FILE, default_domains_content):
        is_first_run = True

    default_credentials_content = ("# Add your credentials here. Format: \n"
                                   "# api_key=YOUR_API_KEY\n"
                                   "# zone_id=YOUR_ZONE_ID\n"
                                   "# email=YOUR_CLOUDFLARE_EMAIL\n"
                                   "[credentials]\n"
                                   "api_key=\n"
                                   "zone_id=\n"
                                   "email=\n")
    if ensure_config_file_exists(CREDENTIALS_CFG_FILE, default_credentials_content):
        is_first_run = True

    return is_first_run


def read_config_file(file_path):
    config = configparser.ConfigParser()
    try:
        config.read(file_path)
    except configparser.DuplicateSectionError as e:
        # print_cyan(f"Error: Duplicate section in configuration file '{file_path}': {e}")
        raise
    return config


def get_domains_config():
    return read_config_file(DOMAINS_CFG_FILE)


def get_credentials_config():
    config = configparser.ConfigParser()
    config.read(CREDENTIALS_CFG_FILE)
    return config['credentials']


def get_domains_without_id():
    config = read_config_file(DOMAINS_CFG_FILE)
    domains_without_id = []

    for section in config.sections():
        if not config[section].get('id'):
            domains_without_id.append({
                'name': section,
                'proxied': config[section].getboolean('proxied', False)
            })

    return domains_without_id


def update_domain_ids(dns_records):
    # Assuming dns_records is a list of dictionaries
    if not isinstance(dns_records, list):
        raise ValueError("Expected a list of DNS records")

    config = read_config_file(DOMAINS_CFG_FILE)
    updated = False

    for record in dns_records:
        # Ensure each record is a dictionary
        if not isinstance(record, dict):
            continue
        domain_name = record.get('name')
        if domain_name and config.has_section(domain_name) and 'id' in record:
            config.set(domain_name, 'id', record['id'])
            updated = True

    if updated:
        with open(DOMAINS_CFG_FILE, 'w') as configfile:
            config.write(configfile)


def validate_credentials():
    credentials = get_credentials_config()
    if not all(credentials.get(key) for key in ['api_key', 'zone_id', 'email']):
        raise ValueError('Missing credentials. Please check your credentials.cfg file.')


def validate_domain_entries():
    domains_config = get_domains_config()
    if not domains_config.sections():
        raise ValueError('No records found to update. Please add at least one domain in dns_records.cfg.')
