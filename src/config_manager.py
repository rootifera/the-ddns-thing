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
                               "# proxied=false\n"
                               "# id=Leave it blank")
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
    """This function gets the domain IDs, so we can query them directly next time"""
    config = read_config_file(DOMAINS_CFG_FILE)
    updated = False

    for record in dns_records.get('result', []):
        domain_name = record.get('name')
        if domain_name and config.has_section(domain_name) and 'id' in record:
            config.set(domain_name, 'id', record['id'])
            updated = True

    if updated:
        with open(DOMAINS_CFG_FILE, 'w') as configfile:
            config.write(configfile)
