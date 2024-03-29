from configparser import DuplicateSectionError

from . import api_operations as api_ops
from . import config_manager as config_manager
from . import ip_fetcher as ip
from . import utils


def main():
    try:
        is_first_run = config_manager.check_and_create_config_files()
        if is_first_run:
            utils.print_red("First run. Please see README")
            return

        credentials = config_manager.get_credentials_config()
        api_token = credentials.get('api_token')

        if not api_ops.verify_api_token(api_token):
            utils.print_red("Invalid API key. Please check your credentials.")
            return

        config_manager.validate_credentials()
        config_manager.validate_domain_entries()

    except ValueError as e:
        utils.print_red(e)
        return

    except DuplicateSectionError as e:
        utils.print_red(f"Configuration Error: {e}")
        return

    public_ip = ip.get_public_ip()
    zone_id = credentials.get('zone_id')
    email = credentials.get('email')

    try:
        dns_records_response = api_ops.list_dns_records(api_token, zone_id, email)
        if isinstance(dns_records_response, dict) and 'result' in dns_records_response:
            dns_records = dns_records_response['result']
            config_manager.update_domain_ids(dns_records)
        else:
            utils.print_red("Error: Unexpected format in DNS records response")
            return
    except Exception as e:
        utils.print_red(f"Error fetching DNS records: {e}")
        return

    domains_config = config_manager.get_domains_config()

    for domain in domains_config.sections():
        domain_details = domains_config[domain]
        if not domain_details.get('id'):
            proxied = domain_details.get('proxied', 'false').lower() == 'true'
            try:
                api_ops.create_dns_record(api_token, zone_id, email, domain, public_ip, proxied)
                utils.print_blue(f"Created DNS record for {domain}")
            except Exception as e:
                utils.print_red(f"Error creating DNS record for {domain}: {e}")

    for domain in domains_config.sections():
        domain_details = domains_config[domain]
        if 'id' in domain_details and domain_details['id']:
            try:
                if api_ops.check_ip_changes_by_id(api_token, zone_id, email, domain_details['id'], public_ip):
                    utils.print_orange(f"Updating IP for {domain}")
                    api_ops.update_record_by_id(api_token, zone_id, email, domain_details['id'], public_ip,
                                                domain_details.get('proxied', 'false').lower() == 'true')
                else:
                    utils.print_green(f"No IP change for {domain}.")
            except Exception as e:
                utils.print_red(f"Error processing {domain}: {e}")


if __name__ == "__main__":
    main()
