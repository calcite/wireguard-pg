# WireGuardPG

WireGuardPG is a utility designed to simplify the configuration and management of a WireGuard server using a PostgreSQL database.
It uses database tables to store and manage WireGuard interface and peer configurations, providing a streamlined approach to dynamically handling VPN settings.
A single database can manage many WireGuard instances with many interfaces.
The application can be integrated into your own application by adding/updating records in the database or using the REST API.

This application can be used by two ways:
- **disabled rest api**  - This case can be used when you want to use WireguardPG as subcomponent of your application. WireguardPG runs as standalone container and reads records/changes from the `server_interface` and `client_peer` tables (the `server_template` table is not required).

- **enabled rest api** - To make changes to the database, the application provides a Rest API.

## Features

- **Database-Driven Configuration:** Manage WireGuard interfaces and peers via records in PostgreSQL database.

- **Dynamic Updates:** Apply changes without having to manually edit files or restart wireguard service. Only changes in interface makes restart the Wireguard interface.

- **Scalable Management:** Easily handle multiple interfaces and peers with a centralized database.

- **Sensitive data (private keys) is not necessarily  be stored in the database.**
  - We can store private key into file mounted into container.


## Database Structure

The PostgreSQL database contains the following tables:

1. `server_interface`

    Stores configuration details for WireGuard interfaces.

    | Column | Type |  | Description |
    | ----------- | ----------- | ----------- | ----------- |
    | id     | SERIAL  |   | Primary key |
    | server_name   | VARCHAR(64) | | Name of WireguardPG instance. The value `default` is default name. |
    | interface_name   | VARCHAR(15) | | Name of interface.  (e.g `wg0`)  |
    | private_key  | VARCHAR(256) |  | Private key or path to private key file. (e.g. `file:///config/private.key`)
    | listen_port | INT | | Listen port |
    | address | TEXT | | IP address of the interface. (e.g `192.168.1.1/24`)
    | dns | VARCHAR(256) | optional | DNS servers.
    | mtu | INT |  optional |
    | fw_mark | INT | optional |
    | table | INT | optional | routing table
    | pre_up | TEXT | optional |
    | post_up | TEXT | optional |
    | pre_down | TEXT | optional |
    | post_down | TEXT | optional |
    | updated_at | TIMESTAMP | NOW() | Automatically set by update
    | created_at | TIMESTAMP | NOW() | Automatically set by create
    | enabled | BOOL | TRUE |

2. `client_peer`

    Stores configuration details for WireGuard peers.

    | Column | Type | | Description |
    | ----------- | ----------- | ----------- | ----------- |
    | id     | SERIAL  |   | Primary key |
    | interface_id  | INT | | reference to interface
    | public_key | VARCHAR(256) | | Public key.
    | address | VARCHAR(256) | | IP address of the peer.
    | name |  VARCHAR(64) | | Name of the peer/user.
    | description |  VARCHAR(256) | optional | Description
    | preshared_key | VARCHAR(256) | optional | Preshared key. |
    | allowed_ips | TEXT | optional | Default value is IP of server interface.
    | updated_at | TIMESTAMP | NOW() | Automatically set by update
    | created_at | TIMESTAMP | NOW() | Automatically set by create
    | enabled | BOOL | TRUE |

3. `server_template`

    This table is required only when is Rest API enabled. It contains default values for peers, IP pool for automatically assign peer's IP address.

    | Column | Type | | Description |
    | ----------- | ----------- | ----------- | ----------- |
    | id     | INT  |   | ID of interface |
    | public_endpoint | VARCHAR(256) | | Public address of WireGuard instance. (e.g. `vpn.example.com:51820`)
    | ip_range | VARCHAR(256) | optional | IP range for automatic assignment to peers. (e.g. `10.10.10.5-10.10.10.254`)
    | public_key | VARCHAR(256) |  | Interface public key. |
    | client_dns | VARCHAR(128) | optional | client DNS servers.
    | client_mtu | INT |  optional |
    | client_fw_mark | INT | optional |
    | client_table | INT | optional |
    | client_pre_up | TEXT | optional |
    | client_post_up | TEXT | optional |
    | client_pre_down | TEXT | optional |
    | client_post_down | TEXT | optional |
    | client_persistent_keepalive | INT |  optional |
    | client_allowed_ips | TEXT | optional | Default value is IP of server interface.


## Requirements

- **WireGuard:** Ensure WireGuard is installed and configured on your system.

- **PostgreSQL:** A PostgreSQL database for storing configurations.

- **Python 3.9+:** The application is built using Python.



## Docker

1. **Environment variables**
    - `SERVER_NAME`: default
    - `DATABASE_URI`: postgres://user:password@localhost:5432/db?options=-c%20search_path=public
    - `DATABASE_INIT`: yes
    - `POSTGRES_POOL_MIN_SIZE`: 5
    - `POSTGRES_POOL_MAX_SIZE`: 10
    - `POSTGRES_CONNECTION_TIMEOUT`: 5
    - `POSTGRES_CONNECTION_CHECK`: 5
    - `CORS_ALLOW_ORIGINS`: *     # comma separated
    - `CORS_ALLOW_METHODS`: *     # comma separated
    - `CORS_ALLOW_HEADERS`: *     # comma separated
    - `CORS_ALLOW_CREDENTIALS`:  yes
    - `WIREGUARD_CONFIG_FOLDER`: /config
    - `API_ENABLED`: no
    - `API_ACCESS_TOKEN`: "<secret>"
    - `LOG_LEVEL`: INFO

1. **Docker-compose**
    ```yaml
    services:
        wireguard:
            image: ghcr.io/calcite/wireguard_pg:latest
            cap_add:
                - NET_ADMIN
                - SYS_MODULE
            sysctls:
                - net.ipv4.conf.all.src_valid_mark=1
            # Uncomment these lines if you want to use API
            #ports:
            #    - 8000:8000
            depends_on:
                - db
            volumes:
                - wg-config:/config
            environment:
                SERVER_NAME: "default"
                DATABASE_URL: "postgresql://dbuser:test@db:5432/devdb"
                # Uncomment these lines if you want to use API
                # API_ENABLED: yes
                # API_ACCESS_TOKEN: "<my-secret-token>"

        db:
            image: postgres:13
            environment:
                POSTGRES_USER: dbuser
                POSTGRES_PASSWORD: test
                POSTGRES_DB: devdb
            volumes:
                - db-data:/var/lib/postgresql/data

        # This container is optional
        adminer:
            image: adminer
            restart: always
            ports:
                - 8080:8080
            depends_on:
                - db
            enviroment:
                ADMINER_DEFAULT_SERVER=pgsql

    volumes:
        db-data:
        wg-config:

    ```

## Example Workflow without API

1. Add a new interface:
    ```sql
    INSERT INTO interface (server_name, interface_name, address, private_key, listen_port)
    VALUES ('default', 'wg0', '10.0.0.1/24', 'your_private_key_here', 51820);
    ```

1. Add a peer to the interface:

    ```sql
    INSERT INTO peer (interface_id, name, public_key, address)
    VALUES (1, 'client1', 'peer_public_key_here', '10.0.0.2/32');
    ```

1. The application detects changes and applies them to the WireGuard server.


## Example Workflow with API
1. Uncomment port definition and environment variables in docker-compose.yml. Set you secure API token by `API_ACCESS_TOKEN`.

1. Start / restart deployment
    ```shell
    docker-compose up -d
    ```
1. Documentation is available on http://localhost:8000/docs or http://localhost:8000/redoc

1. Create a new interface. The private key is store in file. We set `ip_range` for this subnet.
    ```shell
    export API_ACCESS_TOKEN="my-super-secret-token"

    > curl -X POST "http://localhost:8000/api/interface/" \
        -H "Content-Type: application/json" \
        -H "Authorization: $API_ACCESS_TOKEN" \
        -d '{"server_name": "default", "interface_name": "wg1", "private_key": "file:///config/privkey_wg1", "public_key": "MctbQe3QCYTb0BmAK4pfJHQBqc3E4Vtjha42bL7HiWA=", "listen_port": 5123, "public_endpoint": "public_ip_of_this_host:5123", "ip_range": "10.10.11.1 - 10.10.11.255", "address": "10.10.11.1/24"}'
    ```
1. Check our new interface
    ```shell
    > curl "http://localhost:8000/api/interface/" \
        -H "Authorization: $API_ACCESS_TOKEN" | jq
    {
    "public_key": "MctbQe3QCYTb0BmAK4pfJHQBqc3E4Vtjha42bL7HiWA=",
    "public_endpoint": "public_ip_of_this_host:5123",
    "ip_range": "10.10.11.1 - 10.10.11.255",
    "client_dns": null,
    "client_pre_up": null,
    "client_post_up": null,
    "client_pre_down": null,
    "client_post_down": null,
    "client_fw_mark": null,
    "client_persistent_keepalive": null,
    "client_allowed_ips": null,
    "client_mtu": null,
    "client_table": null,
    "server_name": "default",
    "interface_name": "wg1",
    "private_key": "file:///config/privkey_wg1",
    "listen_port": 5123,
    "address": "10.10.11.1/24",
    "dns": null,
    "mtu": null,
    "fw_mark": null,
    "table": null,
    "pre_up": null,
    "post_up": null,
    "pre_down": null,
    "post_down": null,
    "enabled": true,
    "id": 1,
    "updated_at": "2025-02-12T21:38:32.974480Z",
    "created_at": "2025-02-10T10:29:03.120449Z"
    }
    ```
1. Create a new peer. Keys are generated automatically, but private key is not stored.
    ```shell
    > curl -X POST "http://localhost:8000/api/peer/" \
        -H "Content-Type: application/json" \
        -H "Authorization: $API_ACCESS_TOKEN" \
        -d '{"interface_id": 1, "name": "client1"}' | jq

    {
        "interface_id": 1,
        "name": "client1",
        "description": null,
        "public_key": "KW1jkHQrXY6PIK1+IlOEUiUwb3AEh1BzulZNC+MdrUc=",
        "preshared_key": null,
        "persistent_keepalive": null,
        "allowed_ips": "10.10.11.1/32",
        "address": "10.10.11.2/32",
        "enabled": true,
        "id": 1,
        "private_key": "GFaQ+GMqrNY/O+yPeSIH+MNMXAcdbg+c04blv5NOxGk=",
        "client_config": "[Interface]/nPrivateKey = GFaQ+GMqrNY/O+yPeSIH+MNMXAcdbg+c04blv5NOxGk=/n# PublicKey = KW1jkHQrXY6PIK1+IlOEUiUwb3AEh1BzulZNC+MdrUc=/nAddress = 10.10.11.2/32/n/n[Peer]/nPublicKey = MctbQe3QCYTb0BmAK4pfJHQBqc3E4Vtjha42bL7HiWA=/nEndpoint = public_ip_of_this_host:5123/nAllowedIPs = 10.10.11.1/32",
        "updated_at": "2025-01-29T18:47:35.942545Z",
        "created_at": "2025-01-29T18:47:35.942545Z"
    }
    ```

## Contribution

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License.

## Acknowledgments

- WireGuard for providing a secure and efficient VPN solution.

- PostgreSQL for its powerful database capabilities.

