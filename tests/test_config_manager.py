import configparser

from the_ddns_thing import config_manager


def test_ensure_config_dir_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "CONFIG_DIR", str(tmp_path / "config"))
    config_manager.ensure_config_dir_exists()
    assert (tmp_path / "config").exists()


def test_ensure_config_file_exists(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    test_file = config_dir / "test.cfg"
    default_content = "default content"

    monkeypatch.setattr(config_manager, "DNS_RECORDS_CFG_FILE", str(test_file))

    result = config_manager.ensure_config_file_exists(str(test_file), default_content)

    assert result is True
    assert test_file.exists()
    assert test_file.read_text() == default_content


def test_check_and_create_config_files(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    dns_records_cfg = config_dir / "dns_records.cfg"
    credentials_cfg = config_dir / "credentials.cfg"

    monkeypatch.setattr(config_manager, "DNS_RECORDS_CFG_FILE", str(dns_records_cfg))
    monkeypatch.setattr(config_manager, "CREDENTIALS_CFG_FILE", str(credentials_cfg))

    is_first_run = config_manager.check_and_create_config_files()

    assert is_first_run is True
    assert dns_records_cfg.exists()
    assert credentials_cfg.exists()
    assert dns_records_cfg.read_text() == (
        "# Add your dns records here\n"
        "# Format:\n"
        "#\n"
        "# [app.domain.com]\n"
        "# proxied=false\n"
        "# id=Leave it blank"
    )
    assert credentials_cfg.read_text() == (
        "# Add your credentials here. Format: \n"
        "# api_key=YOUR_API_KEY\n"
        "# zone_id=YOUR_ZONE_ID\n"
        "# email=YOUR_CLOUDFLARE_EMAIL\n"
        "[credentials]\n"
        "api_key =\n"
        "zone_id =\n"
        "email =\n"
    )


def test_read_config_file_success(tmp_path):
    config_file = tmp_path / "config.cfg"
    config_content = "[section]\nkey=value\n"
    config_file.write_text(config_content)

    config = config_manager.read_config_file(str(config_file))
    assert config['section']['key'] == 'value'


def test_read_config_file_duplicate_section_error(tmp_path):
    config_file = tmp_path / "config.cfg"
    config_content = "[section]\nkey=value\n[section]\nkey2=value2\n"
    config_file.write_text(config_content)

    with pytest.raises(configparser.DuplicateSectionError):
        config_manager.read_config_file(str(config_file))


def test_get_domains_config(tmp_path, monkeypatch):
    config_file = tmp_path / "dns_records.cfg"
    config_content = "[example.com]\nproxied=false\nid=12345678\n"
    config_file.write_text(config_content)

    monkeypatch.setattr(config_manager, "DNS_RECORDS_CFG_FILE", str(config_file))

    config = config_manager.get_domains_config()

    assert config.has_section('example.com')
    assert config.get('example.com', 'proxied') == 'false'
    assert config.get('example.com', 'id') == '12345678'


def test_get_credentials_config(tmp_path, monkeypatch):
    credentials_file = tmp_path / "credentials.cfg"
    credentials_content = """
    [credentials]
    api_key=test_api_key
    zone_id=test_zone_id
    email=test@example.com
    """
    credentials_file.write_text(credentials_content)
    monkeypatch.setattr(config_manager, "CREDENTIALS_CFG_FILE", str(credentials_file))
    credentials_config = config_manager.get_credentials_config()

    assert credentials_config.get('api_key') == 'test_api_key'
    assert credentials_config.get('zone_id') == 'test_zone_id'
    assert credentials_config.get('email') == 'test@example.com'


def test_get_domains_without_id(tmp_path, monkeypatch):
    dns_records_file = tmp_path / "dns_records.cfg"
    dns_records_content = """
    [domain_with_id.com]
    proxied=true
    id=12345678

    [domain_without_id.com]
    proxied=false

    [another_domain_without_id.com]
    proxied=true
    """
    dns_records_file.write_text(dns_records_content)
    monkeypatch.setattr(config_manager, "DNS_RECORDS_CFG_FILE", str(dns_records_file))
    domains_without_id = config_manager.get_domains_without_id()

    assert len(domains_without_id) == 2
    assert domains_without_id == [
        {'name': 'domain_without_id.com', 'proxied': False},
        {'name': 'another_domain_without_id.com', 'proxied': True}
    ]


def test_update_domain_ids(tmp_path, monkeypatch):
    dns_records_file = tmp_path / "dns_records.cfg"
    dns_records_content = """
    [example.com]
    proxied=true

    [anotherexample.com]
    proxied=false
    """
    dns_records_file.write_text(dns_records_content)

    monkeypatch.setattr(config_manager, "DNS_RECORDS_CFG_FILE", str(dns_records_file))

    mock_dns_records = [
        {'name': 'example.com', 'id': '12345'},
        {'name': 'nonexistent.com', 'id': '67890'},  # not in config
        {'name': 'anotherexample.com', 'id': '54321'}
    ]

    config_manager.update_domain_ids(mock_dns_records)

    updated_config = configparser.ConfigParser()
    updated_config.read(str(dns_records_file))

    assert updated_config['example.com']['id'] == '12345'
    assert 'nonexistent.com' not in updated_config
    assert updated_config['anotherexample.com']['id'] == '54321'


import pytest


def test_validate_credentials_missing_values(tmp_path, monkeypatch):
    credentials_file = tmp_path / "credentials.cfg"
    credentials_content = """
    [credentials]
    api_key=
    zone_id=test_zone_id
    email=test@example.com
    """
    credentials_file.write_text(credentials_content)

    monkeypatch.setattr(config_manager, "CREDENTIALS_CFG_FILE", str(credentials_file))

    with pytest.raises(ValueError, match='Missing credentials. Please check your credentials.cfg file.'):
        config_manager.validate_credentials()


def test_validate_domain_entries_no_entries(tmp_path, monkeypatch):
    dns_records_file = tmp_path / "dns_records.cfg"
    dns_records_file.write_text("")

    monkeypatch.setattr(config_manager, "DNS_RECORDS_CFG_FILE", str(dns_records_file))

    with pytest.raises(ValueError,
                       match='No records found to update. Please add at least one domain in dns_records.cfg.'):
        config_manager.validate_domain_entries()
