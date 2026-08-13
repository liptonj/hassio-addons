# JGROK Agent

The JGROK Agent connects Home Assistant and other reachable local services to
JGROK through one outbound secure connection. It does not publish an inbound
container port.

On first start, open the add-on log and approve the displayed five-character
device code. The resulting device credential is kept in Home Assistant's
persistent add-on storage and reused after restarts, upgrades, and backups.

See [DOCS.md](DOCS.md) for installation and registration instructions.

Prebuilt `amd64` and `aarch64` images are published on Docker Hub as the
multi-architecture container `5lsus/jgrok`.
