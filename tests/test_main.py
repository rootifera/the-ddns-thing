import configparser
from unittest.mock import patch

import pytest

import the_ddns_thing
import the_ddns_thing.main as main_module
from the_ddns_thing import config_manager


@patch('the_ddns_thing.config_manager.check_and_create_config_files')
@patch('the_ddns_thing.utils.print_red')
def test_main_first_run(mock_print_red, mock_check_and_create_config_files):
    mock_check_and_create_config_files.return_value = True
    with pytest.raises(SystemExit):
        main_module.main()


@patch('the_ddns_thing.config_manager.check_and_create_config_files', return_value=False)
@patch('the_ddns_thing.api_operations.verify_api_key', return_value=False)
@patch('the_ddns_thing.config_manager.get_credentials_config')
@patch('the_ddns_thing.utils.print_red')
def test_main_invalid_api_key(mock_print_red, mock_get_credentials_config, mock_verify_api_key,
                              mock_check_and_create_config_files):
    mock_get_credentials_config.return_value = {'api_key': 'invalid_key', 'zone_id': 'zone_id',
                                                'email': 'email@example.com'}

    main_module.main()
    mock_verify_api_key.assert_called_once_with('invalid_key')
    mock_print_red.assert_called_once_with("Invalid API key. Please check your credentials.")


def test_validate_credentials_success():
    with patch('the_ddns_thing.config_manager.get_credentials_config') as mock_get_config:
        mock_get_config.return_value = {'api_key': 'test_api_key', 'zone_id': 'test_zone_id',
                                        'email': 'test@example.com'}
        try:
            config_manager.validate_credentials()
        except ValueError:
            pytest.fail("validate_credentials() raised ValueError unexpectedly!")


def test_validate_credentials_failure():
    with patch('the_ddns_thing.config_manager.get_credentials_config') as mock_get_config:
        mock_get_config.return_value = {'api_key': 'test_api_key', 'zone_id': '', 'email': 'test@example.com'}
        with pytest.raises(ValueError):
            config_manager.validate_credentials()


def mock_config_with_section(section_name):
    config = configparser.ConfigParser()
    config.add_section(section_name)
    config.set(section_name, 'proxied', 'False')
    config.set(section_name, 'id', '123')
    return config


def test_validate_domain_entries_success():
    with patch('the_ddns_thing.config_manager.get_domains_config',
               return_value=mock_config_with_section("example.com")):
        try:
            config_manager.validate_domain_entries()
        except ValueError:
            pytest.fail("validate_domain_entries raised ValueError unexpectedly!")


def test_validate_domain_entries_failure():
    with patch('the_ddns_thing.config_manager.get_domains_config', return_value=configparser.ConfigParser()):
        with pytest.raises(ValueError):
            config_manager.validate_domain_entries()


def test_main_invalid_api_key():
    with patch('the_ddns_thing.api_operations.verify_api_key', return_value=False):
        with patch('the_ddns_thing.config_manager.validate_credentials'):
            with patch('the_ddns_thing.config_manager.validate_domain_entries'):
                with pytest.raises(SystemExit):
                    the_ddns_thing.main.main()


@patch('the_ddns_thing.api_operations.requests.get')
@patch('the_ddns_thing.ip_fetcher.get_public_ip')
@patch('the_ddns_thing.config_manager.check_and_create_config_files', return_value=False)
@patch('the_ddns_thing.api_operations.verify_api_key', return_value=True)
@patch('the_ddns_thing.config_manager.validate_credentials')
@patch('the_ddns_thing.config_manager.validate_domain_entries')
@patch('the_ddns_thing.config_manager.get_credentials_config',
       return_value={'api_key': 'test_api_key', 'zone_id': 'test_zone_id', 'email': 'test@example.com'})
def test_main_ip_fetch_success(mock_get_credentials_config, mock_validate_domain_entries, mock_validate_credentials,
                               mock_verify_api_key,
                               mock_check_config_files, mock_get_public_ip, mock_requests_get):
    mock_get_public_ip.return_value = "192.0.2.1"
    mock_response = mock_requests_get.return_value
    mock_response.json.return_value = {'result': []} 
    mock_response.status_code = 200

    main_module.main()

    mock_verify_api_key.assert_called_once_with('test_api_key')


@patch('the_ddns_thing.config_manager.validate_domain_entries')
@patch('the_ddns_thing.config_manager.validate_credentials')
@patch('the_ddns_thing.api_operations.verify_api_key', return_value=True)
@patch('the_ddns_thing.config_manager.check_and_create_config_files', return_value=False)
@patch('the_ddns_thing.ip_fetcher.get_public_ip')
def test_main_ip_fetch_failure(mock_get_public_ip, mock_check_config_files, mock_verify_api_key,
                               mock_validate_credentials, mock_validate_domain_entries):
    mock_get_public_ip.side_effect = Exception("IP fetch failed")

    with pytest.raises(SystemExit):
        the_ddns_thing.main.main()
