"""Create step-ca's own MariaDB database and users.

Runs once per add-on start with the MariaDB add-on's service account, which
is only used here. step-ca gets a user limited to its database; the
management page gets a read-only user.
"""

import os
import sys

import pymysql

# Add-ons reach MariaDB from Supervisor's internal network, the same host
# patterns the MariaDB add-on uses for its own logins.
HOSTS = ("172.30.32.%", "172.30.33.%")


def main():
    database = os.environ["DB_NAME"]
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
        for user, password, privileges in users:
            for host in HOSTS:
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (user, host, password))
                cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (user, host, password))
                cur.execute(f"GRANT {privileges} ON `{database}`.* TO %s@%s", (user, host))


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001 - reported to run.sh
        print(err, file=sys.stderr)
        sys.exit(1)
