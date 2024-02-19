import ip_fetcher as ip_fetcher
import config_manager as config_manager


def main():
    try:
        public_ip = ip_fetcher.get_public_ip()
        print(f"Public IP: {public_ip}")
        # Rest of your application logic...
    except Exception as e:
        print(f"Error: {e}")

    config_manager.check_and_create_config_files()


if __name__ == "__main__":
    main()
