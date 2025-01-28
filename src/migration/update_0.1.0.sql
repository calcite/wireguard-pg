CREATE TABLE "interface" (
  "id" serial NOT NULL,
  PRIMARY KEY ("id"),
  "server_name" character varying(64) NOT NULL,
  "interface_name" character varying(64) NOT NULL,
  "private_key" character varying(256) NOT NULL,
  "public_key" character varying(256) NULL,
  "listen_port" integer NOT NULL,
  "address" character varying(256) NOT NULL,
  "dns" character varying(256) NULL,
  "public_endpoint" character varying(256) NULL,
  "ip_range" character varying(256) NULL,
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
COMMENT ON COLUMN "interface"."server_name" IS 'wireguard instance name';
COMMENT ON COLUMN "interface"."interface_name" IS 'wireguard interface name';
COMMENT ON TABLE "interface" IS 'Wireguard interfaces';

ALTER TABLE "interface"
ADD CONSTRAINT "interface_server_name_interface_name" UNIQUE ("server_name", "interface_name");


CREATE TABLE "peer" (
  "id" serial NOT NULL,
  PRIMARY KEY ("id"),
  "interface_id" integer NOT NULL,
  "name" character varying(64) NOT NULL,
  "description" character varying(256) NULL,
  "public_key" character varying(256) NOT NULL,
  "preshared_key" character varying(256) NULL,
  "persistent_keepalive" integer NULL,
  "allowed_ips" character varying(512) NOT NULL,
  "endpoint" character varying(256) NULL,
  "address" character varying(256) NOT NULL,
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "enabled" boolean NOT NULL DEFAULT true
);

ALTER TABLE "peer"
ADD FOREIGN KEY ("interface_id") REFERENCES "interface" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

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
BEFORE UPDATE ON interface
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER data_interface_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON interface
FOR EACH ROW
EXECUTE FUNCTION notify_data_change();

CREATE TRIGGER trigger_peer_set_updated_at
BEFORE UPDATE ON peer
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER data_peer_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON peer
FOR EACH ROW
EXECUTE FUNCTION notify_data_change();

