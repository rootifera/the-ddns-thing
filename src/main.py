import api_operations as api_ops
import config_manager as config_manager
import ip_fetcher as ip


def main():
    credentials = config_manager.get_credentials_config()
    public_ip = ip.get_public_ip()

    api_key = credentials.get('api_key')
    zone_id = credentials.get('zone_id')
    email = credentials.get('email')

    try:
        dns_records = api_ops.list_dns_records(api_key, zone_id, email)
        config_manager.update_domain_ids(dns_records)
    except Exception as e:
        print(f"Error fetching DNS records: {e}")

    domains_config = config_manager.get_domains_config()
    for domain in domains_config.sections():
        if not domains_config[domain].get('id'):
            proxied = domains_config[domain].get('proxied', 'false').lower() == 'true'
            try:
                api_ops.create_dns_record(api_key, zone_id, email, domain, public_ip, proxied)
                print(f"Created DNS record for {domain}")
            except Exception as e:
                print(f"Error creating DNS record for {domain}: {e}")


if __name__ == "__main__":
    main()
