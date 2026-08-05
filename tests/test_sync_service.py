from the_ddns_thing import sync_service


def _domain(domain_id, root_domain, zone_id):
    return {"id": domain_id, "root_domain": root_domain, "zone_id": zone_id}


def _subdomain(subdomain_id, domain_id, name, record_id):
    return {
        "id": subdomain_id,
        "domain_id": domain_id,
        "name": name,
        "record_id": record_id,
        "proxied": 0,
    }


def _configure_cycle(mocker, domains, subdomains):
    mocker.patch.object(sync_service.db, "is_setup_complete", return_value=True)
    mocker.patch.object(sync_service.db, "get_runtime_config", return_value={
        "cloudflare_email": "test@example.com",
        "cloudflare_api_key": "test-key",
    })
    mocker.patch.object(sync_service.db, "list_domains", return_value=domains)
    mocker.patch.object(sync_service.db, "list_subdomains", return_value=subdomains)
    mocker.patch.object(sync_service.db, "update_subdomain_record")
    mocker.patch.object(sync_service.db, "record_subdomain_ip")
    mocker.patch.object(sync_service.db, "update_sync_status")
    mocker.patch.object(sync_service.ip_fetcher, "get_public_ip", return_value="4.3.2.1")


def test_sync_updates_record_found_on_aggregated_record_list(mocker):
    domains = [_domain(1, "example.com", "zone-1")]
    subdomains = [_subdomain(10, 1, "home", "record-1")]
    _configure_cycle(mocker, domains, subdomains)
    mocker.patch.object(sync_service.api_operations, "list_dns_records", return_value={
        "result": [{
            "id": "record-1",
            "name": "home.example.com",
            "content": "1.2.3.4",
            "proxied": False,
        }]
    })
    update = mocker.patch.object(sync_service.api_operations, "update_record_by_id")

    result = sync_service.run_sync_cycle()

    assert result["status"] == "ok"
    update.assert_called_once()
    assert "updated 1" in result["summary"]
    sync_service.db.update_sync_status.assert_called_once_with(
        "ok", result["summary"], "", "4.3.2.1"
    )


def test_sync_continues_after_one_record_fails(mocker):
    domains = [_domain(1, "example.com", "zone-1")]
    subdomains = [
        _subdomain(10, 1, "broken", "record-1"),
        _subdomain(11, 1, "working", "record-2"),
    ]
    _configure_cycle(mocker, domains, subdomains)
    mocker.patch.object(sync_service.api_operations, "list_dns_records", return_value={
        "result": [
            {"id": "record-1", "name": "broken.example.com", "content": "1.1.1.1", "proxied": False},
            {"id": "record-2", "name": "working.example.com", "content": "2.2.2.2", "proxied": False},
        ]
    })
    update = mocker.patch.object(
        sync_service.api_operations,
        "update_record_by_id",
        side_effect=[ValueError("permission denied"), None],
    )

    result = sync_service.run_sync_cycle()

    assert update.call_count == 2
    assert result["status"] == "error"
    assert result["errors"] == ["broken.example.com: permission denied"]
    assert "updated 1" in result["summary"]
    assert "failed 1" in result["summary"]


def test_sync_continues_after_one_zone_cannot_be_listed(mocker):
    domains = [
        _domain(1, "broken.example", "zone-1"),
        _domain(2, "working.example", "zone-2"),
    ]
    subdomains = [
        _subdomain(10, 1, "home", "record-1"),
        _subdomain(11, 2, "home", "record-2"),
    ]
    _configure_cycle(mocker, domains, subdomains)
    mocker.patch.object(
        sync_service.api_operations,
        "list_dns_records",
        side_effect=[
            ValueError("zone unavailable"),
            {"result": [{
                "id": "record-2",
                "name": "home.working.example",
                "content": "4.3.2.1",
                "proxied": False,
            }]},
        ],
    )
    update = mocker.patch.object(sync_service.api_operations, "update_record_by_id")

    result = sync_service.run_sync_cycle()

    update.assert_not_called()
    assert result["status"] == "error"
    assert result["errors"] == ["broken.example: zone unavailable"]
    assert "unchanged 1" in result["summary"]
