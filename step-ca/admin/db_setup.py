"""Create Step CA's MariaDB schema, users, and resident onboarding tables.

Runs once per add-on start with the MariaDB add-on's service account, which
is only used here. The CA gets access to its database, the certificate page
gets read-only access, and resident onboarding gets access only to its resident
tables. All resident and key metadata is created in MariaDB.
"""

import os
import sys

import pymysql

# Add-ons reach MariaDB from Supervisor's internal network, the same host
# patterns the MariaDB add-on uses for its own logins.
HOSTS = ("172.30.32.%", "172.30.33.%")


def main():
    database = os.environ["DB_NAME"]
    portal_user = os.environ["PORTAL_USER"]
    portal_password = os.environ["PORTAL_PASSWORD"]
    users = (
        (os.environ["RW_USER"], os.environ["RW_PASSWORD"], "ALL PRIVILEGES"),
        (os.environ["RO_USER"], os.environ["RO_PASSWORD"], "SELECT"),
    )
    conn = pymysql.connect(
        host=os.environ["ADMIN_HOST"],
        port=int(os.environ["ADMIN_PORT"]),
        user=os.environ["ADMIN_USER"],
        password=os.environ["ADMIN_PASSWORD"],
        connect_timeout=10,
        autocommit=True,
    )
    # The database name is restricted to [A-Za-z0-9_] by the add-on schema;
    # accounts and passwords are passed as parameters.
    with conn, conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        conn.select_db(database)
        cur.execute(f"""CREATE TABLE IF NOT EXISTS `{database}`.`stepca_residents` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `name` VARCHAR(100) NOT NULL,
            `email` VARCHAR(254) NOT NULL,
            `unit` VARCHAR(80) NOT NULL DEFAULT '',
            `ipsk_id` VARCHAR(191) NOT NULL,
            `ipsk_name` VARCHAR(128) NOT NULL,
            `created_at` DATETIME NOT NULL,
            `source_ip` VARCHAR(45) NULL,
            `mac_address` CHAR(17) NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_stepca_residents_email` (`email`),
            UNIQUE KEY `uq_stepca_residents_ipsk` (`ipsk_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        # Upgrade already-created resident tables without changing imported rows.
        cur.execute(f"ALTER TABLE `{database}`.`stepca_residents` ADD COLUMN IF NOT EXISTS `source_ip` VARCHAR(45) NULL")
        cur.execute(f"ALTER TABLE `{database}`.`stepca_residents` ADD COLUMN IF NOT EXISTS `mac_address` CHAR(17) NULL")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS `{database}`.`stepca_invites` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `code_hash` CHAR(64) NOT NULL,
            `created_by` VARCHAR(128) NOT NULL,
            `created_at` DATETIME NOT NULL,
            `used_at` DATETIME NULL,
            `revoked_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_stepca_invites_hash` (`code_hash`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        cur.execute(f"ALTER TABLE `{database}`.`stepca_invites` ADD COLUMN IF NOT EXISTS `expires_at` DATETIME NULL")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS `{database}`.`stepca_resident_accounts` (
            `owner_key` VARCHAR(260) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
            `name` VARCHAR(100) NOT NULL,
            `email` VARCHAR(254) NOT NULL,
            PRIMARY KEY (`owner_key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS `{database}`.`stepca_resident_devices` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `owner_key` VARCHAR(260) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
            `device_name` VARCHAR(100) NOT NULL,
            `unit` VARCHAR(80) NOT NULL DEFAULT '',
            `mac_address` CHAR(17) NOT NULL,
            `ipsk_id` VARCHAR(191) NOT NULL,
            `source_ip` VARCHAR(45) NULL,
            `verified` BOOLEAN NOT NULL DEFAULT FALSE,
            `active` BOOLEAN NOT NULL DEFAULT TRUE,
            `created_at` DATETIME NOT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_stepca_devices_mac` (`mac_address`),
            UNIQUE KEY `uq_stepca_devices_ipsk` (`ipsk_id`),
            KEY `ix_stepca_devices_owner` (`owner_key`),
            FOREIGN KEY (`owner_key`) REFERENCES `stepca_resident_accounts` (`owner_key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        # Uniqueness applies to current keys; revoked records remain available for history.
        # RTRIM keeps indexed CHAR expressions independent of MariaDB's
        # PAD_CHAR_TO_FULL_LENGTH mode (otherwise MariaDB rejects the column).
        for table in ("stepca_residents", "stepca_resident_devices"):
            cur.execute(f"ALTER TABLE `{database}`.`{table}` ADD COLUMN IF NOT EXISTS `active` BOOLEAN NOT NULL DEFAULT TRUE")
            cur.execute(f"ALTER TABLE `{database}`.`{table}` ADD COLUMN IF NOT EXISTS `active_mac` CHAR(17) "
                        "GENERATED ALWAYS AS (CASE WHEN active THEN RTRIM(mac_address) ELSE NULL END) STORED")
            cur.execute(f"ALTER TABLE `{database}`.`{table}` ADD UNIQUE INDEX IF NOT EXISTS `uq_stepca_active_mac` (`active_mac`)")
            old_index = "uq_stepca_residents_mac" if table == "stepca_residents" else "uq_stepca_devices_mac"
            cur.execute(f"ALTER TABLE `{database}`.`{table}` DROP INDEX IF EXISTS `{old_index}`")
        cur.execute(f"ALTER TABLE `{database}`.`stepca_residents` ADD COLUMN IF NOT EXISTS `active_email` VARCHAR(254) "
                    "GENERATED ALWAYS AS (CASE WHEN active THEN email ELSE NULL END) STORED")
        cur.execute(f"ALTER TABLE `{database}`.`stepca_residents` ADD UNIQUE INDEX IF NOT EXISTS `uq_stepca_active_email` (`active_email`)")
        cur.execute(f"ALTER TABLE `{database}`.`stepca_residents` DROP INDEX IF EXISTS `uq_stepca_residents_email`")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS `{database}`.`stepca_ipsks` (
            `ipsk_id` VARCHAR(191) NOT NULL,
            `network_id` VARCHAR(80) NOT NULL,
            `ssid_number` TINYINT UNSIGNED NOT NULL,
            `associated_user` VARCHAR(254) NOT NULL DEFAULT '',
            `associated_unit` VARCHAR(80) NOT NULL DEFAULT '',
            `status` VARCHAR(16) NOT NULL DEFAULT 'active',
            `created_at` DATETIME NOT NULL,
            PRIMARY KEY (`ipsk_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        for user, password, privileges in users:
            for host in HOSTS:
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (user, host, password))
                cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (user, host, password))
                cur.execute(f"GRANT {privileges} ON `{database}`.* TO %s@%s", (user, host))
        for host in HOSTS:
            cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",
                        (portal_user, host, portal_password))
            cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (portal_user, host, portal_password))
            cur.execute(
                f"GRANT SELECT, INSERT, UPDATE ON `{database}`.`stepca_residents` TO %s@%s",
                (portal_user, host),
            )
            cur.execute(
                f"GRANT SELECT, INSERT, UPDATE ON `{database}`.`stepca_invites` TO %s@%s",
                (portal_user, host),
            )
            cur.execute(f"GRANT SELECT, INSERT, UPDATE ON `{database}`.`stepca_resident_accounts` TO %s@%s", (portal_user, host))
            cur.execute(f"GRANT SELECT, INSERT, UPDATE ON `{database}`.`stepca_ipsks` TO %s@%s", (portal_user, host))
            cur.execute(f"GRANT SELECT, INSERT, UPDATE ON `{database}`.`stepca_resident_devices` TO %s@%s", (portal_user, host))


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001 - reported to run.sh
        print(err, file=sys.stderr)
        sys.exit(1)
