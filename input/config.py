{
    "threads": 1,
    "cooldown": 90,
    "provider_selection": "mailcow",
    "email_providers": {
        "mailcow": {
            "enabled": true,
            "mailcow_url": "https://mail.botnix.in",
            "api_key": "A6667D-BA307C-EAE5C3-3925C4-B2A936",
            "keyid": "jxdze@349#$%^&*",
            "imap_host": "mail.botnix.in",
            "domains": [
                "nixonmart.me"
            ],
            "description": "Custom Mailcow server - creates mailboxes via REST API, reads inbox via IMAP"
        },
        "hotmail007": {
            "enabled": true,
            "client_key": "H7-038DE5304042A7",
            "api_key": "",
            "domain": "hotmail.com",
            "description": "Hotmail007 - Premium Hotmail email accounts"
        },
        "zeusx": {
            "enabled": false,
            "api_key": "4978a937d20528",
            "client_key": "4978a937c1a106844328",
            "domain": "hotmail.com",
            "description": "ZeusX - Premium Zeus email accounts"
        },
        "draxono": {
            "name": "public temp inbox",
            "enabled": true,
            "api_key": "duk_cwIQIRq3d-s-RSHE",
            "domains": [
                "tuffgys.sbs",
                "coldmails.shop",
                "muskbiz.quest", 
                "muskbiz.sbs",
                "sastacart.xyz",
                "socialnos.bond"
            ],
            "api_base": "https://mail.draxono.in",
            "description": "No auth required. Throwaway inboxes on public domains."
        },
        "yopmail": {
            "enabled": false,
            "base_url": "https://yopmail.com",
            "api_base": "",
            "description": "Yopmail - Free disposable email service, no authentication required"
        }
    },
    "proxy": {
        "enabled": false,
        "file": "input/proxies.txt"
    },
    "mullvad": {
        "enabled": false,
        "country": "sg",
        "auto_login": true,
        "account_number": "9934867432061972",
        "account_file": "input/mullvad_accounts.txt"
    },
    "nopecha": {
        "enabled": true,
        "api_key": "ocuk3f1qry02awz9"
    },
    "adb": {
        "enabled": false,
        "path": "C:\\LDPlayer\\LDPlayer9\\adb.exe",
        "host": "127.0.0.1",
        "port": 5555
    }
}
