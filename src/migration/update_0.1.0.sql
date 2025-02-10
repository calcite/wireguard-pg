CREATE TABLE "server_interface" (
  "id" serial NOT NULL,
  PRIMARY KEY ("id"),
  "server_name" character varying(64) NOT NULL,
  "interface_name" character varying(15) NOT NULL,
  "private_key" character varying(256) NOT NULL,
  "public_key" character varying(256) NULL,
  "listen_port" integer NOT NULL,
  "address" character varying(256) NOT NULL,
  "dns" character varying(256) NULL,
  "mtu" integer NULL,
  "fw_mark" integer NULL,
  "table" character varying(32) NULL,
  "pre_up" text NULL,
  "post_up" text NULL,
  "pre_down" text NULL,
  "post_down" text NULL,
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "enabled" boolean NOT NULL DEFAULT true
);
COMMENT ON COLUMN "server_interface"."server_name" IS 'wireguard instance name';
COMMENT ON COLUMN "server_interface"."interface_name" IS 'wireguard interface name';
COMMENT ON TABLE "server_interface" IS 'Wireguard interfaces';

ALTER TABLE "server_interface"
ADD CONSTRAINT "server_interface_server_name_interface_name" UNIQUE ("server_name", "interface_name");


CREATE TABLE "client_peer" (
  "id" serial NOT NULL,
  PRIMARY KEY ("id"),
  "interface_id" integer NOT NULL,
  "name" character varying(64) NOT NULL,
  "description" character varying(256) NULL,
  "public_key" character varying(256) NOT NULL,
  "preshared_key" character varying(256) NULL,
  "persistent_keepalive" integer NULL,
  "allowed_ips" character varying(512) NULL,
  "address" character varying(256) NOT NULL,
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "enabled" boolean NOT NULL DEFAULT true
);

ALTER TABLE "client_peer"
ADD FOREIGN KEY ("interface_id") REFERENCES "server_interface" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION notify_data_change()
RETURNS TRIGGER AS $$
DECLARE
table_name TEXT := TG_TABLE_NAME;
payload JSON;
BEGIN
    payload := json_build_object(
        'old', row_to_json(OLD),
        'new', row_to_json(NEW)
    );
    PERFORM pg_notify(table_name, payload::TEXT);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER trigger_interface_set_updated_at
BEFORE UPDATE ON server_interface
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER data_interface_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON server_interface
FOR EACH ROW
EXECUTE FUNCTION notify_data_change();

CREATE TRIGGER trigger_peer_set_updated_at
BEFORE UPDATE ON client_peer
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER data_peer_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON client_peer
FOR EACH ROW
EXECUTE FUNCTION notify_data_change();


CREATE TABLE "server_template" (
  "interface_id" integer NOT NULL,
  "public_endpoint" character varying(128) NOT NULL,
  "ip_range" character varying(255) NULL,
  "client_dns" character varying(128) NULL,
  "client_pre_up" text NULL,
  "client_post_up" text NULL,
  "client_pre_down" text NULL,
  "client_post_down" text NULL,
  "client_fw_mark" integer NULL,
  "client_persistent_keepalive" integer NULL,
  "client_allowed_ip" character varying(512) NULL,
  "client_mtu" integer NULL,
  "client_table" character varying(32) NULL,
  "client_interface_name" character varying(15) NULL
);
ALTER TABLE "server_template"
ADD FOREIGN KEY ("interface_id") REFERENCES "server_interface" ("id") ON DELETE CASCADE