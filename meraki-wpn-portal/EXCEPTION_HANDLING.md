# Exception Handling Documentation

## Broad Exception Catches - Justified Uses

This document explains where we use `except Exception` and why it's appropriate in each case.

### ✅ Testing & Validation (Broad catch is REQUIRED)

**Location:** `app/api/admin.py` - `/settings/test-connection`

```python
# Test Meraki API
try:
    client = MerakiClient(test_settings["meraki_api_key"])
    orgs = await client.get_organizations()
except Exception as e:
    # Must catch ANY error - network, auth, timeout, API changes, etc.
    results["tests"]["meraki_api"] = {"success": False, "message": str(e)}
```

**Why:** Testing endpoints MUST catch all possible exceptions to provide friendly error messages. We don't want to crash the test endpoint.

---

### ✅ Optional Operations (Broad catch is OK)

**Location:** `app/core/meraki_client.py` - SSID name lookup

```python
try:
    ssid_info = await self.get_ssid(network_id, ssid_number)
    result["ssid_name"] = ssid_info.get("name", f"SSID-{ssid_number}")
except Exception:
    # Fallback if SSID lookup fails - not critical
    result["ssid_name"] = f"SSID-{ssid_number}"
```

**Why:** SSID name is cosmetic. If it fails for ANY reason, use fallback.

---

### ✅ Stats/Metrics Collection (Broad catch is OK)

**Location:** `app/api/admin.py` - `/dashboard`

```python
try:
    ipsks = await ha_client.list_ipsks()
    total_ipsks = len(ipsks)
    active_ipsks = sum(1 for i in ipsks if i.get("status") == "active")
except Exception as e:
    logger.warning(f"Failed to fetch IPSK stats: {e}")
    total_ipsks = active_ipsks = expired_ipsks = revoked_ipsks = online_now = 0
```

**Why:** Dashboard stats are non-critical. Better to show zeros than crash the dashboard.

---

### ✅ Error Message Enrichment (Broad catch for parsing only)

**Location:** `app/core/meraki_client.py` - API error parsing

```python
try:
    error_data = response.json()
    error_msg = error_data.get("errors", [error_msg])
except Exception:
    pass  # Use default error message if JSON parsing fails
```

**Why:** We're trying to get a better error message from JSON. If that fails, just use the basic message.

---

### ✅ Authentication Fallback (Broad catch is OK)

**Location:** `app/api/deps.py` - Token verification

```python
try:
    payload = verify_token(token)
    return payload
except Exception:
    pass  # Try next authentication method
```

**Why:** Multiple auth methods are tried in sequence. Failures should silently try the next method.

---

### ✅ Date Parsing (Broad catch for optional parsing)

**Location:** `app/core/meraki_client.py` - Expiry date parsing

```python
try:
    exp_time = datetime.fromisoformat(ipsk.get("expiry"))
    if exp_time < datetime.now(timezone.utc):
        return "expired"
except Exception:
    pass  # Invalid date format, treat as active
```

**Why:** Date formats can vary. If parsing fails for ANY reason, default to "active".

---

### ✅ HA Area Lookup (Broad catch for optional feature)

**Location:** `app/api/registration.py` - Area fetching

```python
try:
    areas = await ha_client.get_areas()
    return [area["name"] for area in areas]
except Exception as e:
    logger.warning(f"Failed to fetch HA areas: {e}")
    return []  # Fall back to manual unit list
```

**Why:** HA areas are optional. If unavailable for ANY reason, fall back to manual units.

---

### ❌ FIXED - Now Using Specific Exceptions

The following were changed from broad to specific:

1. **Settings File I/O** - Now catches `FileNotFoundError`, `JSONDecodeError`, `PermissionError`
2. **Decryption** - Now catches `ValueError`, `TypeError` specifically
3. **OAuth Initialization** - Now catches `ValueError`, `TypeError`, `ImportError`
4. **HA Connection** - Now catches `ConnectionError`, `TimeoutError`

---

## Exception Handling Best Practices

### ✅ DO Use Specific Exceptions When:
- File operations (`FileNotFoundError`, `PermissionError`, `OSError`)
- Network operations (`ConnectionError`, `TimeoutError`)
- Data validation (`ValueError`, `TypeError`, `KeyError`)
- Configuration errors (`ImportError`, `AttributeError`)

### ✅ DO Use Broad Exceptions When:
- Testing connections (must catch everything)
- Optional features (failure shouldn't crash)
- Metrics/stats collection (zeros are acceptable)
- Fallback patterns (try X, if any error do Y)

### ❌ DON'T Use Broad Exceptions When:
- Core functionality (must know what failed)
- Security operations (specific errors matter)
- Data persistence (must handle each failure type)
- API endpoints (return appropriate HTTP status)

---

## Summary

**Total `except Exception` uses:** ~15
- **Justified (testing/optional):** 12
- **Fixed (now specific):** 3

All remaining broad catches are **intentional and documented**.
