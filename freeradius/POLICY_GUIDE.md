# Policy Management Guide

## Overview

The FreeRADIUS Policy Management system provides flexible, database-driven authorization policies with support for VLAN assignment, bandwidth limiting, time-based restrictions, and custom RADIUS attributes.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Policy Structure](#policy-structure)
3. [Creating Policies](#creating-policies)
4. [Match Conditions](#match-conditions)
5. [Reply Attributes](#reply-attributes)
6. [Time Restrictions](#time-restrictions)
7. [Priority System](#priority-system)
8. [Testing Policies](#testing-policies)
9. [Best Practices](#best-practices)
10. [Examples](#examples)

---

## Key Concepts

### What is a Policy?

A **policy** is a set of rules that determines what happens when a user or device attempts to authenticate. Policies can:

- Match specific users, devices, or network conditions
- Assign VLANs for network segmentation
- Limit bandwidth (upload/download speeds)
- Set session timeouts
- Add custom RADIUS attributes
- Restrict access by time of day or day of week

### Priority-Based Evaluation

Policies are evaluated in **priority order** (0 = highest priority). The **first matching policy** is applied. This allows you to create specific policies for exceptions and general policies for defaults.

### Policy Groups

Policies can be organized into **groups** (e.g., "guests", "employees", "iot") for easier management and organization.

---

## Policy Structure

A policy consists of:

```python
{
    "name": "unique-policy-name",
    "description": "What this policy does",
    "priority": 100,  # Lower = higher priority
    "group_name": "guests",  # Optional grouping
    "policy_type": "user",  # user, device, network, group
    
    # Match Conditions (who/what this applies to)
    "match_username": "guest.*",  # Regex pattern
    "match_mac_address": "aa:bb:cc:.*",
    "match_nas_identifier": "office-ap-.*",
    "match_nas_ip": "192\\.168\\.1\\..*",
    
    # VLAN Assignment
    "vlan_id": 100,
    "vlan_name": "Guest_Network",
    
    # Bandwidth Limits (kbps)
    "bandwidth_limit_up": 5000,    # Upload
    "bandwidth_limit_down": 10000,  # Download
    
    # Session Controls
    "session_timeout": 3600,  # seconds
    "idle_timeout": 600,
    "max_concurrent_sessions": 2,
    
    # Custom Attributes
    "reply_attributes": [...],
    "check_attributes": [...],
    
    # Time Restrictions
    "time_restrictions": {...},
    
    # Status
    "is_active": true
}
```

---

## Creating Policies

### API Endpoint

```http
POST /api/policies
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json
```

### Basic Policy Example

```json
{
  "name": "guest-wifi",
  "description": "Guest wireless access with limited bandwidth",
  "priority": 100,
  "group_name": "guests",
  "match_username": "guest.*",
  "vlan_id": 100,
  "bandwidth_limit_down": 10000,
  "bandwidth_limit_up": 5000,
  "session_timeout": 3600,
  "idle_timeout": 600,
  "is_active": true
}
```

### Response

```json
{
  "id": 1,
  "name": "guest-wifi",
  "priority": 100,
  "usage_count": 0,
  "created_at": "2026-01-14T12:00:00Z",
  ...
}
```

---

## Match Conditions

Match conditions determine **who or what** the policy applies to. All match conditions support **regex patterns**.

### Username Matching

```json
{
  "match_username": "guest.*"  // Matches guest1, guest-user, etc.
}
```

**Examples:**
- `"admin.*"` - All admin users
- `"^employee-[0-9]+$"` - employee-123, employee-456
- `"contractor@.*"` - Any contractor email-style username

### MAC Address Matching

```json
{
  "match_mac_address": "^aa:bb:cc:.*"  // Matches MACs starting with aa:bb:cc
}
```

**Examples:**
- `"^00:11:22:.*"` - Specific vendor OUI
- `".*:.*:.*:.*:.*:ff$"` - MACs ending in :ff

### NAS Identifier Matching

```json
{
  "match_nas_identifier": "office-ap-.*"  // Matches office-ap-1, office-ap-2, etc.
}
```

### NAS IP Matching

```json
{
  "match_nas_ip": "192\\.168\\.1\\..*"  // Matches 192.168.1.x
}
```

**Note:** Escape dots in IP addresses: `192\\.168\\.1\\.100`

### Multiple Conditions

All specified match conditions must be satisfied (AND logic):

```json
{
  "match_username": "guest.*",
  "match_nas_identifier": "guest-ap-.*"
}
```
This matches guest users connecting through guest access points.

---

## Reply Attributes

Reply attributes are RADIUS attributes sent back in Access-Accept messages.

### Standard Reply Attributes

```json
{
  "reply_attributes": [
    {
      "attribute": "Reply-Message",
      "operator": ":=",
      "value": "Welcome to Guest Network"
    },
    {
      "attribute": "Session-Timeout",
      "operator": ":=",
      "value": "3600"
    },
    {
      "attribute": "Idle-Timeout",
      "operator": ":=",
      "value": "600"
    }
  ]
}
```

### VLAN Attributes (Auto-Generated)

When you set `vlan_id`, these attributes are automatically added:

```
Tunnel-Type := VLAN
Tunnel-Medium-Type := IEEE-802
Tunnel-Private-Group-Id := 100
```

### Bandwidth Attributes (Auto-Generated)

When you set bandwidth limits, these Filter-Id attributes are added:

```
Filter-Id += "rate-limit:downstream:10000"
Filter-Id += "rate-limit:upstream:5000"
```

### Common RADIUS Attributes

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `Reply-Message` | Message to user | "Welcome" |
| `Session-Timeout` | Max session duration | "3600" (1 hour) |
| `Idle-Timeout` | Max idle time | "600" (10 min) |
| `Acct-Interim-Interval` | Accounting updates | "300" (5 min) |
| `Class` | Session classification | "premium-user" |

### Operators

- `:=` - Set (overwrite)
- `+=` - Add (append)
- `==` - Equal (check)
- `!=` - Not equal
- `>`, `<`, `>=`, `<=` - Comparison

---

## Time Restrictions

Control when a policy is active based on day of week and time of day.

### Structure

```json
{
  "time_restrictions": {
    "days_of_week": [0, 1, 2, 3, 4],  // 0=Monday, 6=Sunday
    "time_start": "09:00",
    "time_end": "17:00",
    "timezone": "America/New_York"
  }
}
```

### Examples

**Business Hours Only:**
```json
{
  "time_restrictions": {
    "days_of_week": [0, 1, 2, 3, 4],  // Weekdays
    "time_start": "08:00",
    "time_end": "18:00",
    "timezone": "America/Los_Angeles"
  }
}
```

**Weekend Access:**
```json
{
  "time_restrictions": {
    "days_of_week": [5, 6],  // Saturday, Sunday
    "timezone": "UTC"
  }
}
```

**Night Hours:**
```json
{
  "time_restrictions": {
    "time_start": "18:00",
    "time_end": "06:00",  // Wraps to next day
    "timezone": "America/New_York"
  }
}
```

---

## Priority System

### How Priority Works

1. Policies are sorted by priority (0 = highest)
2. Each authentication request is evaluated against policies in order
3. The **first matching policy** is applied
4. Remaining policies are skipped

### Priority Strategy

**Use low priorities (0-50) for:**
- Exceptions and special cases
- VIP users
- Emergency access

**Use medium priorities (51-100) for:**
- Regular user policies
- Department-specific policies

**Use high priorities (101-200) for:**
- Default policies
- Catch-all rules

### Example Priority Structure

```
Priority 10: admin-users        (Admins get full access)
Priority 50: employee-wireless  (Employees get VLAN 200)
Priority 100: guest-wireless    (Guests get VLAN 100, limited)
Priority 200: default-deny      (Catch-all, reject unknown)
```

### Reordering Policies

```http
POST /api/policies/reorder
Authorization: Bearer YOUR_TOKEN

{
  "1": 10,   // Policy ID 1 -> Priority 10
  "2": 20,   // Policy ID 2 -> Priority 20
  "3": 30    // Policy ID 3 -> Priority 30
}
```

---

## Testing Policies

Test policies before activating them using the test endpoint.

### Test Endpoint

```http
POST /api/policies/{policy_id}/test
Authorization: Bearer YOUR_TOKEN

{
  "username": "guest123",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "nas_identifier": "office-ap-1",
  "nas_ip": "192.168.1.10"
}
```

### Response

```json
{
  "matches": true,
  "policy_id": 1,
  "policy_name": "guest-wifi",
  "reply_attributes": [
    {
      "attribute": "Tunnel-Type",
      "operator": ":=",
      "value": "VLAN"
    },
    ...
  ],
  "reason": "All match conditions satisfied"
}
```

### Testing Workflow

1. Create policy with `is_active: false`
2. Test with various scenarios
3. Refine match conditions
4. Activate policy with `is_active: true`

---

## Best Practices

### 1. Use Descriptive Names

✅ **Good:** `guest-wifi-limited-bandwidth`  
❌ **Bad:** `policy1`

### 2. Add Detailed Descriptions

```json
{
  "name": "contractor-access",
  "description": "Contractors: VLAN 150, 8AM-6PM weekdays, 5Mbps down, expires after 8 hours"
}
```

### 3. Test Before Activating

Always test policies with `is_active: false` first.

### 4. Use Groups for Organization

Group related policies:
- `guests` - Guest network policies
- `employees` - Employee policies
- `iot` - IoT device policies
- `contractors` - Temporary access

### 5. Monitor Usage

Check `usage_count` and `last_used` to identify:
- Unused policies (can be removed)
- Frequently used policies (may need optimization)

### 6. Priority Gaps

Leave gaps in priorities for future policies:
```
10, 20, 30, 40...  (Not 1, 2, 3, 4...)
```

### 7. Document Regex Patterns

```json
{
  "match_username": "^guest-[0-9]{4}$",
  "description": "Matches guest-1234, guest-5678 format only"
}
```

### 8. Default Deny Policy

Always have a lowest-priority catch-all policy:

```json
{
  "name": "default-deny",
  "priority": 999,
  "description": "Reject all unmatched requests",
  "is_active": true
}
```

---

## Examples

### Example 1: Guest Network

**Requirement:** Guest users with limited access

```json
{
  "name": "guest-network",
  "description": "Guest WiFi: VLAN 100, 1 hour session, 10Mbps",
  "priority": 100,
  "group_name": "guests",
  "match_username": "guest.*",
  "vlan_id": 100,
  "vlan_name": "Guest_Network",
  "bandwidth_limit_down": 10000,
  "bandwidth_limit_up": 5000,
  "session_timeout": 3600,
  "idle_timeout": 600,
  "max_concurrent_sessions": 1,
  "is_active": true
}
```

### Example 2: Employee Network

**Requirement:** Full access for employees

```json
{
  "name": "employee-network",
  "description": "Employee access: VLAN 200, full speed, 8 hours",
  "priority": 50,
  "group_name": "employees",
  "match_username": "^[a-z]+\\.[a-z]+@company\\.com$",
  "vlan_id": 200,
  "vlan_name": "Corporate_Network",
  "session_timeout": 28800,
  "is_active": true
}
```

### Example 3: IoT Devices

**Requirement:** Isolated network for IoT

```json
{
  "name": "iot-devices",
  "description": "IoT: VLAN 300, restricted, specific MAC vendor",
  "priority": 150,
  "group_name": "iot",
  "match_mac_address": "^b8:27:eb:.*",  // Raspberry Pi vendor
  "vlan_id": 300,
  "vlan_name": "IoT_Network",
  "max_concurrent_sessions": 1,
  "is_active": true
}
```

### Example 4: Time-Restricted Contractor

**Requirement:** Business hours only

```json
{
  "name": "contractor-weekday",
  "description": "Contractors: weekdays 8AM-6PM only",
  "priority": 75,
  "group_name": "contractors",
  "match_username": "contractor-.*",
  "vlan_id": 150,
  "session_timeout": 28800,
  "time_restrictions": {
    "days_of_week": [0, 1, 2, 3, 4],
    "time_start": "08:00",
    "time_end": "18:00",
    "timezone": "America/New_York"
  },
  "is_active": true
}
```

### Example 5: VIP Users

**Requirement:** High priority, no limits

```json
{
  "name": "vip-users",
  "description": "VIP: Priority access, no restrictions",
  "priority": 10,
  "group_name": "vip",
  "match_username": "^(ceo|cto|cfo)@company\\.com$",
  "vlan_id": 250,
  "reply_attributes": [
    {
      "attribute": "Class",
      "operator": ":=",
      "value": "VIP-Priority"
    }
  ],
  "is_active": true
}
```

---

## Troubleshooting

### Policy Not Matching

1. **Check priority order** - Higher priority policy may be matching first
2. **Test regex patterns** - Use online regex testers
3. **Check is_active** - Policy must be active
4. **Use test endpoint** - See detailed match results

### Multiple Policies Matching

Only the **first** matching policy is applied. Adjust priorities.

### Policy Not Generated in FreeRADIUS

1. Check database watcher logs
2. Verify policy file: `/etc/raddb/policies`
3. Restart FreeRADIUS: `radmin -e 'hup'`

### Performance Issues

- Limit regex complexity
- Use indexed fields for matching
- Consider policy consolidation

---

## API Reference

### List Policies
```http
GET /api/policies?page=1&page_size=50&is_active=true&group_name=guests
```

### Get Policy
```http
GET /api/policies/{id}
```

### Create Policy
```http
POST /api/policies
```

### Update Policy
```http
PUT /api/policies/{id}
```

### Delete Policy
```http
DELETE /api/policies/{id}
```

### Test Policy
```http
POST /api/policies/{id}/test
```

### List Groups
```http
GET /api/policies/groups
```

### Reorder Policies
```http
POST /api/policies/reorder
```

---

## Next Steps

- Review [API Quick Start](API_QUICKSTART.md)
- Explore [RadSec Setup](RADSEC_SETUP.md)
- Read [Enterprise Features](ENTERPRISE_FEATURES.md)
