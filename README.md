# WireGuardPG

WireGuardPG is a utility designed to simplify the configuration and management of a WireGuard server using a PostgreSQL database.
It uses database tables to store and manage WireGuard interface and peer configurations, providing a streamlined approach to dynamically handling VPN settings.
A single database can manage many WireGuard instances with many interfaces.
The application can be integrated into your own application by adding/updating records in the database or using the REST API.

## Features

- **Database-Driven Configuration:** Manage WireGuard interfaces and peers via records in PostgreSQL database.

- **Dynamic Updates:** Apply changes without having to manually edit files or restart wireguard service.

- **Scalable Management:** Easily handle multiple interfaces and peers with a centralized database.

- **Sensitive data (private keys) is not necessarily  be stored in the database.**
  - We can store private key into file mounted into container.


## Database Structure

The PostgreSQL database contains the following tables:

1. `interface`

    Stores configuration details for WireGuard interfaces.

    | Column | Type |  | Description |
    | ----------- | ----------- | ----------- | ----------- |
    | id     | SERIAL  |   | Primary key |
    | namserver_name   | VARCHAR(64) | | Name of application instance. |
    | interface_name   | VARCHAR(64) | | Name of interface.    |
    | private_key  | VARCHAR(256) |  | Private key or path to private key file. (e.g. `file:///config/private.key`)
    | public_key | VARCHAR(256) | optional; used by API | Public key. |
    | listen_port | INT | | Listen port |
    | address | VARCHAR(256) | | IP address of the interface.
    | dns | VARCHAR(256) | optional; used by API | DNS servers.
    | public_endpoint | VARCHAR(256) | optional; used by API | Public address with port of WireGuard instance.
    | ip_range | VARCHAR(256) | optional; used by API | IP subnet for automatically assign to peers.
    | mtu | INT |  optional |
    | fw_mark | INT | optional |
    | table | VARCHAR(32) | optional | routing table
    | pre_up | TEXT | optional |
    | post_up | TEXT | optional |
    | pre_down | TEXT | optional |
    | post_down | TEXT | optional |
    | updated_at | TIMESTAMP | NOW() | Automatically set by update
    | created_at | TIMESTAMP | NOW() | Automatically set by create
    | enabled | BOOL | TRUE |

2. `peer`

    Stores configuration details for WireGuard peers.

    | Column | Type | | Description |
    | ----------- | ----------- | ----------- | ----------- |
    | id     | SERIAL  |   | Primary key |
    | interface_id  | INT | | reference to interface
    | name |  VARCHAR(64) | | Name of the peer/user.
    | description |  VARCHAR(256) | optional | Description
    | public_key | VARCHAR(256) | optional | Public key.
    | preshared_key | VARCHAR(256) | optional | Preshared key. |
    | persistent_keepalive | INT | optional | in seconds
    | allowed_ips | VARCHAR(256) |  |
    | address | VARCHAR(256) | | IP address of the peer.
    | updated_at | TIMESTAMP | NOW() | Automatically set by update
    | created_at | TIMESTAMP | NOW() | Automatically set by create
    | enabled | BOOL | TRUE |

## Requirements

- **WireGuard:** Ensure WireGuard is installed and configured on your system.

- **PostgreSQL:** A PostgreSQL database for storing configurations.

- **Python 3.9+:** The application is built using Python.



## Docker

1. **Environment variables**
    - `SERVER_NAME`: default
    - `DATABASE_URI`: postgres://user:password@localhost:5432/db?options=-c%20search_path=public
    - `DATABASE_INIT`: yes
    - `DATABASE_INTERFACE_TABLE_NAME`: interface
    - `DATABASE_PEER_TABLE_NAME`: peer
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
                SERVER_NAME: "main_vpn"
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
    INSERT INTO interface (server_name, interface_name, address, private_key, public_key, public_endpoint, listen_port)
    VALUES ('default', 'wg0', '10.0.0.1', 'your_private_key_here', 'public_key_here', 'peer_endpoint_here:51820', 51820);
    ```

1. Add a peer to the interface:

    ```sql
    INSERT INTO peer (interface_id, name, public_key, allowed_ips, address)
    VALUES (1, 'client1', 'peer_public_key_here', '10.0.0.2/32', '10.0.0.2');
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
        -d '{"server_name": "default", "interface_name": "wg1", "private_key": "file:///config/privkey_wg1", "public_key": "MctbQe3QCYTb0BmAK4pfJHQBqc3E4Vtjha42bL7HiWA=", "listen_port": 5123, "public_endpoint": "public_ip_of_this_host:5123", "ip_range": "10.10.11.1 - 10.10.11.255"}'
    ```
1. Check our new interface
    ```shell
    > curl "http://localhost:8000/api/interface/" \
        -H "Authorization: $API_ACCESS_TOKEN" | jq
    {
        "id": 1,
        "server_name": "default",
        "interface_name": "wg1",
        "private_key": "file:///config/privkey_wg1",
        "public_key": "MctbQe3QCYTb0BmAK4pfJHQBqc3E4Vtjha42bL7HiWA=",
        "listen_port": 5123,
        "address": "10.10.11.1",
        "dns": null,
        "public_endpoint": "public_ip_of_this_host:5123",
        "ip_range": "10.10.11.1 - 10.10.11.255",
        "mtu": null,
        "fw_mark": null,
        "table": null,
        "pre_up": null,
        "post_up": null,
        "pre_down": null,
        "post_down": null,
        "enabled": true,
        "updated_at": "2025-01-29T13:32:32.999401Z",
        "created_at": "2025-01-27T19:58:32.531101Z"
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
        "allowed_ips": "0.0.0.0/0",
        "address": "10.10.11.2",
        "enabled": true,
        "id": 1,
        "private_key": "GFaQ+GMqrNY/O+yPeSIH+MNMXAcdbg+c04blv5NOxGk=",
        "client_config": "[Interface]/nPrivateKey = GFaQ+GMqrNY/O+yPeSIH+MNMXAcdbg+c04blv5NOxGk=/n# PublicKey = KW1jkHQrXY6PIK1+IlOEUiUwb3AEh1BzulZNC+MdrUc=/nAddress = 10.10.11.2/n/n[Peer]/nPublicKey = MctbQe3QCYTb0BmAK4pfJHQBqc3E4Vtjha42bL7HiWA=/nEndpoint = public_ip_of_this_host:5123/nAllowedIPs = 0.0.0.0/0",
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

