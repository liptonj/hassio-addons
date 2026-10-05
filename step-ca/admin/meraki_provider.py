"""Choose one Meraki transport before a request performs any writes."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

SETTINGS_OVERRIDE = None
SERVICE = None


class ProviderUnavailable(RuntimeError):
    """The bridge explicitly has no provider or no supported command."""


def settings():
    if SETTINGS_OVERRIDE is not None:
        return dict(SETTINGS_OVERRIDE)
    try:
        with open("/data/options.json", encoding="utf-8") as source:
            return json.load(source).get("meraki") or {}
    except FileNotFoundError:
        return json.loads(os.environ.get("MERAKI_SETTINGS_JSON", "{}"))


def validate(config):
    if config.get("source", "auto") not in ("auto", "meraki_ha", "api_key"):
        raise ValueError("Choose a Meraki connection source.")
    key = config.get("api_key") or ""
    if key and (not isinstance(key, str) or len(key) > 512 or any(c.isspace() for c in key)):
        raise ValueError("Enter the Meraki API key without spaces.")
    if config.get("source") == "api_key" and not key:
        raise ValueError("Enter an API key for the direct connection.")
    org = config.get("organization_id") or ""
    if org and not org.isdigit():
        raise ValueError("Enter the numeric Meraki organization ID, or leave it blank to discover organizations.")


def available(supervisor_token):
    config = settings()
    return bool(supervisor_token or config.get("api_key"))


def service_class():
    global SERVICE
    if SERVICE is None:
        path = Path(__file__).with_name("meraki_service.py")
        if not path.exists():
            path = Path(__file__).resolve().parents[1] / "custom_components/step_ca_scep/meraki_ipsk.py"
        spec = importlib.util.spec_from_file_location("stepca_meraki_service", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        SERVICE = module.MerakiIpsk
    return SERVICE


async def direct_call(config, messages):
    import meraki.aio
    validate(config)
    if not config.get("api_key"):
        raise ProviderUnavailable("Connect Meraki HA or save a Meraki API key under Settings → Meraki → Connection.")
    try:
        async with asyncio.timeout(55):
            # No SDK request logging: writes can contain client passphrases.
            # Do not automatically retry an uncertain write.
            async with meraki.aio.AsyncDashboardAPI(
                    api_key=config["api_key"], output_log=False, print_console=False,
                    suppress_logging=True, maximum_retries=1, single_request_timeout=15) as dashboard:
                org = config.get("organization_id")
                rows = [{"id": org}] if org else await dashboard.organizations.getOrganizations()
                async def refresh():
                    return None
                clients = [SimpleNamespace(organization_id=str(row["id"]), dashboard=dashboard,
                                           async_ensure_token_valid=refresh) for row in rows]
                service = service_class()(clients)
                results = []
                for message in messages:
                    action = message["type"].removeprefix("step_ca_scep/ipsk/")
                    if action == "options":
                        result = await service.options(message.get("network_id", ""))
                        result["provider"] = "api_key"
                    elif action == "access_manager":
                        result = await service.access_manager(message["network_id"])
                    elif action == "list":
                        result = await service.list(message.get("scopes", []))
                    elif action in ("create", "configuration_plan", "configure", "client_key_plan", "assign_client_key"):
                        result = await getattr(service, action)(message)
                    elif action in ("get", "reveal_passphrase", "revoke", "delete"):
                        result = await service.key(action, message.get("ipsk_id"), message.get("network_id", ""), message.get("ssid_number", 0))
                    else:
                        raise ValueError("Unsupported Meraki operation.")
                    results.append(result)
                return results
    except ValueError:
        raise
    except Exception:
        raise RuntimeError("Meraki did not confirm the request. Check API permissions, organization features and Dashboard before retrying a write.") from None


async def call(core, messages, supervisor_token):
    config = settings()
    validate(config)
    if config.get("source", "auto") != "api_key":
        try:
            if not supervisor_token:
                raise ProviderUnavailable("The Home Assistant Meraki bridge is unavailable.")
            # Probe before any mutation. Never switch providers after a write,
            # authentication failure, timeout or API rejection.
            await core({"type": "step_ca_scep/ipsk/options", "network_id": ""})
        except ProviderUnavailable:
            if config.get("source") == "meraki_ha":
                raise
        else:
            return await core(*messages)
    return await direct_call(config, messages)
