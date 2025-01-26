# WireGuard Database Manager

WireGuard Database Manager is a utility designed to simplify the configuration and management of a WireGuard server using a PostgreSQL database. It leverages database tables to store and manage WireGuard interface and peer configurations, providing a streamlined approach to dynamically handle VPN settings.

## Features

- **Database-Driven Configuration:** Manage WireGuard interfaces and peers via PostgreSQL tables.

- **Dynamic Updates:** Apply changes without manual configuration file edits.

- **Scalable Management:** Easily handle multiple interfaces and peers with a centralized database.

## Database Structure

The PostgreSQL database contains the following tables:

1. `interface`

    Stores configuration details for WireGuard interfaces.

    | Column | Type |  | Description |
    | ----------- | ----------- | ----------- | ----------- |
    | id     | SERIAL  |   | Primary key |
    | namserver_name   | VARCHAR(64) | | Name of application instance. |
    | interface_name   | VARCHAR(64) | | Name of interface.    |
    | private_key  | VARCHAR(256) |  | Private key or path to private key file.
    | public_key | VARCHAR(256) | optional | Public key. |
    | listen_port | INT | | Listen port |
    | address | VARCHAR(256) | | IP address of the interface.
    | dns | VARCHAR(256) | optional | DNS servers.
    | public_endpoint | VARCHAR(256) | optional | Public address with port of WireGuard instance.
    | subnet | VARCHAR(256) | optional | IP subnet for automatically assign to peers.
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
    | private_key | VARCHAR(256) | optional | Private key.
    | public_key | VARCHAR(256) | | Public key. |
    | preshared_key | VARCHAR(256) | optional | Preshared key. |
    | persistent_keepalive | INT | optional | in seconds
    | allowed_ips | VARCHAR(256) | |
    | endpoint | VARCHAR(256) | optional | Server endpoint
    | address | VARCHAR(256) | | IP address of the peer.
    | updated_at | TIMESTAMP | NOW() | Automatically set by update
    | created_at | TIMESTAMP | NOW() | Automatically set by create
    | enabled | BOOL | TRUE |

## Requirements

- **WireGuard:** Ensure WireGuard is installed and configured on your system.

- **PostgreSQL:** A PostgreSQL database for storing configurations.

- **Python 3.9+:** The application is built using Python.



## Usage

1. **Start the Application:**

   ```shell
    python -m uvicorn app:app
    ```

1. **Add Interfaces and Peers:**

    - Use your preferred PostgreSQL client to insert records into the interface and peer tables.

1. **Apply Changes to WireGuard:**

    - The application reads the database changes and updates WireGuard configurations accordingly.

## Docker

1. **Build docker container**
    ```shell
    docker build -t wireguard-pg:local .
    ```

1. **Environment variables**
    - `SERVER_NAME`: default
    - `JWT_SECRET`: <secret>
    - `DATABASE_URI`: postgres://user:password@localhost:5432/db
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
    - `ENABLE_API`: no
    - `LOG_LEVEL`: INFO

1. **Run docker container**
    ```shell
    > docker run --rm -it --name wg1 -e LOG_LEVEL=debug -v (pwd)/tmp:/config --pid=host --cap-add NET_ADMIN --cap-add SYS_MODULE --network host -e DATABASE_URI=postgresql://dbuser:test@db_server:5432/db wireguard-pg:local
    ```

## Example Workflow

1. Add a new interface:
    ```sql
    INSERT INTO interface (server_name, interface_name, address, private_key, public_key, listen_port)
    VALUES ('default', 'wg0', '10.0.0.1', 'your_private_key_here', 'public_key_here', 51820);
    ```

1. Add a peer to the interface:

    ```sql
    INSERT INTO peer (interface_id, name, public_key, allowed_ips, endpoint, address)
    VALUES (1, 'client1', 'peer_public_key_here', '10.0.0.2/32', 'peer_endpoint_here:51820', '10.0.0.2');
    ```

1. The application detects changes and applies them to the WireGuard server.

## Contribution

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License.

## Acknowledgments

- WireGuard for providing a secure and efficient VPN solution.

- PostgreSQL for its powerful database capabilities.

