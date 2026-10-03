"""Exercise real MariaDB schemas, privileges, upgrades and registration races.

Run inside the Step CA image on an isolated Docker network whose subnet matches
Home Assistant (172.30.33.0/24). Set ADMIN_HOST/PORT/USER/PASSWORD to a disposable
MariaDB instance. Only databases named stepca_audit_fresh/stepca_audit_legacy
are created. Wi-Fi calls are fixtures; no network keys or certificates are issued.
"""
import concurrent.futures
import datetime
import json
import os
import sys
import threading
import time
from unittest.mock import patch

sys.path.insert(0, '/opt/step-ca-admin')
import db_setup
import ipsk
import resident_access
import pymysql

os.environ.setdefault('ADMIN_PORT', '3306')
os.environ.setdefault('ADMIN_USER', 'root')
checks = []


def root_connect(database=None):
    return pymysql.connect(host=os.environ['ADMIN_HOST'], port=int(os.environ['ADMIN_PORT']),
        user=os.environ['ADMIN_USER'], password=os.environ['ADMIN_PASSWORD'],
        database=database, autocommit=True, connect_timeout=3, read_timeout=10,
        cursorclass=pymysql.cursors.DictCursor)


def query(sql, args=()):
    with root_connect(os.environ['DB_NAME']) as conn, conn.cursor() as cur:
        cur.execute(sql,args)
        return cur.fetchall()


def assert_denied(sql, user, password):
    with pymysql.connect(host=os.environ['ADMIN_HOST'], user=user, password=password,
                         database=os.environ['DB_NAME'], autocommit=True) as conn, conn.cursor() as cur:
        try:
            cur.execute(sql)
        except pymysql.MySQLError as err:
            assert err.args[0] in (1142,1143), err
        else:
            raise AssertionError('Unexpected database privilege: ' + sql)


def seed_legacy_schema():
    name=os.environ['DB_NAME']
    with root_connect() as conn, conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE `{name}`')
        conn.select_db(name)
        cur.execute('''CREATE TABLE stepca_residents (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL, email VARCHAR(254) NOT NULL,
            unit VARCHAR(80) NOT NULL DEFAULT '', ipsk_id VARCHAR(191) NOT NULL,
            ipsk_name VARCHAR(128) NOT NULL, created_at DATETIME NOT NULL,
            source_ip VARCHAR(45), mac_address CHAR(17),
            UNIQUE KEY uq_stepca_residents_email(email),
            UNIQUE KEY uq_stepca_residents_ipsk(ipsk_id),
            UNIQUE KEY uq_stepca_residents_mac(mac_address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''')
        cur.execute('''CREATE TABLE stepca_invites (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            code_hash CHAR(64) NOT NULL, created_by VARCHAR(128) NOT NULL,
            created_at DATETIME NOT NULL, used_at DATETIME, revoked_at DATETIME,
            UNIQUE KEY uq_stepca_invites_hash(code_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''')
        cur.execute("INSERT INTO stepca_residents (name,email,ipsk_id,ipsk_name,created_at,mac_address) "
                    "VALUES ('Old device','old@example.org','old-key','Old',UTC_TIMESTAMP(),'00:11:22:33:44:99')")


def run_schema(name):
    os.environ.update(DB_NAME=name, RW_USER=name+'_ca', RW_PASSWORD='fixture-ca',
        RO_USER=name+'_read', RO_PASSWORD='fixture-read', PORTAL_USER=name+'_portal',
        PORTAL_PASSWORD='fixture-portal',
        PORTAL_DB_HOST=os.environ['ADMIN_HOST'], PORTAL_DB_PORT=os.environ['ADMIN_PORT'],
        PORTAL_DB_USER=name+'_portal', PORTAL_DB_PASSWORD='fixture-portal',
        RESIDENT_SETTINGS_JSON=json.dumps({'network_id':'N_fixture','ssid_number':0,'duration_hours':0}))
    if name.endswith('legacy'):
        seed_legacy_schema()
    db_setup.main()
    db_setup.main()
    code=ipsk.create_invite('Fixture administrator', label='Unit 1 — onboarding')
    assert ipsk.list_invites()[0]['label']=='Unit 1 — onboarding'
    checks.append(name+': invitation labels persist after additive schema upgrade')
    query('UPDATE stepca_invites SET used_at=UTC_TIMESTAMP() WHERE code_hash=SHA2(%s,256)',(code,))
    db_setup.main()
    assert query('SELECT used_at FROM stepca_invites WHERE code_hash=SHA2(%s,256)',(code,))[0]['used_at'] is not None
    checks.append(name+': repeated setup preserves consumed invitations')

    query('CREATE TABLE x509_certs (id INT PRIMARY KEY)')
    assert_denied('SELECT * FROM x509_certs',name+'_portal','fixture-portal')
    assert_denied('INSERT INTO x509_certs VALUES (1)',name+'_read','fixture-read')
    with ipsk.db_connect() as conn,conn.cursor() as cur:
        cur.execute('SELECT CURRENT_USER() AS account')
        assert cur.fetchone()['account'].endswith('@172.30.33.%')
        cur.execute('SELECT * FROM stepca_resident_devices')
    checks.append(name+': limited portal and read-only certificate privileges')

    key={'id':'N_fixture:0:metadata-key','network_id':'N_fixture','ssid_number':0,
         'ssid_name':'Fixture Wi-Fi','passphrase':'fixture-password'}
    ipsk._record_key(key,'Unit 1','Fixture Resident')
    record=ipsk._key_records()[0]
    assert record['associated_user']=='Fixture Resident' and record['associated_unit']=='Unit 1'
    columns={row['Field'] for row in query('SHOW COLUMNS FROM stepca_ipsks')}
    assert 'passphrase' not in columns and 'password' not in columns
    with patch.object(ipsk,'core_call',return_value=[{}]):
        ipsk.set_ipsk_status(key['id'],'revoke')
    assert ipsk._key_records()[0]['status']=='revoked'
    assert_denied('DELETE FROM stepca_ipsks',name+'_portal','fixture-portal')
    checks.append(name+': key attribution and revocation history stored only in MariaDB without passwords')

    counter=[0]
    mutex=threading.Lock()
    cleanup=[]
    def create(*args,**kwargs):
        with mutex:
            counter[0]+=1
            ident='fixture-key-'+str(counter[0])
        return {'id':ident,'ssid_name':'Fixture Wi-Fi','passphrase':'fixture-password'}
    config={'network_id':'N_fixture','ssid_number':0,'invite_required':False,'max_devices_per_resident':5}
    def identity(owner):
        return {'owner':owner,'name':'Fixture Resident','email':owner+'@example.org','verified':True}
    def device(owner,mac,cfg=config):
        try:
            return resident_access.create_device(ipsk,cfg,identity(owner),'TV',mac,'','','192.0.2.1')
        except ValueError as err:
            return str(err)
    with patch.object(ipsk,'inactive_ipsk_ids',return_value=[]), \
            patch.object(ipsk,'create_ipsk',side_effect=create), \
            patch.object(ipsk,'set_ipsk_status',side_effect=lambda ident,action:cleanup.append((ident,action))), \
            patch.object(ipsk,'INVITE_REQUIRED',False):
        first='00:11:22:33:44:01'
        result=device('one',first)
        assert isinstance(result,dict),result
        row=query('SELECT * FROM stepca_resident_devices WHERE mac_address=%s AND active=TRUE',(first,))[0]
        query('UPDATE stepca_resident_devices SET active=FALSE WHERE id=%s',(row['id'],))
        assert isinstance(device('one',first),dict)
        assert query('SELECT COUNT(*) AS n FROM stepca_resident_devices WHERE mac_address=%s',(first,))[0]['n']==2
        assert query('SELECT COUNT(*) AS n FROM stepca_resident_devices WHERE active_mac=%s',(first,))[0]['n']==1
        checks.append(name+': revoked device history and replacement MAC')

        legacy_mac='00:11:22:33:44:02'
        ipsk.register_resident('Legacy Resident','legacy@example.org','','','192.0.2.1',legacy_mac)
        query('UPDATE stepca_residents SET active=FALSE WHERE email=%s',('legacy@example.org',))
        ipsk.register_resident('Legacy Resident','legacy@example.org','','','192.0.2.1',legacy_mac)
        assert query('SELECT COUNT(*) AS n FROM stepca_residents WHERE email=%s',('legacy@example.org',))[0]['n']==2
        assert query('SELECT COUNT(*) AS n FROM stepca_residents WHERE active_email=%s',('legacy@example.org',))[0]['n']==1
        checks.append(name+': revoked legacy email/MAC can be replaced')

        before_count=counter[0]
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda owner:device(owner,'00:11:22:33:44:03'),['race-a','race-b']))
        assert sum(isinstance(r,dict) for r in results)==1,results
        assert counter[0]==before_count+1
        checks.append(name+': concurrent same-MAC registration creates one remote key')


        before_count=counter[0]
        def cross_flow(kind):
            try:
                if kind == "legacy":
                    return ipsk.register_resident('Cross Resident','cross@example.org','','',
                                                  '192.0.2.1','00:11:22:33:44:08')
                return device('cross-self','00:11:22:33:44:08')
            except ValueError as err:
                return str(err)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(cross_flow,['legacy','self']))
        assert sum(isinstance(r,dict) for r in results)==1,results
        assert counter[0]==before_count+1
        checks.append(name+': legacy/self-service race creates one remote key across both tables')

        before_count=counter[0]
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda mac:device('quota',mac,{**config,'max_devices_per_resident':1}),
                                 ['00:11:22:33:44:04','00:11:22:33:44:05']))
        assert sum(isinstance(r,dict) for r in results)==1,results
        assert counter[0]==before_count+1
        checks.append(name+': concurrent owner quota cannot be exceeded')

        code=ipsk.create_invite('Fixture administrator')
        query('UPDATE stepca_invites SET expires_at=%s WHERE code_hash=SHA2(%s,256)',(datetime.datetime(2000,1,1),code))
        before_count=counter[0]
        try:
            resident_access.create_device(ipsk,{**config,'invite_required':True},identity('expired'),'TV',
                                          '00:11:22:33:44:06','',code,'192.0.2.1')
        except ValueError as err:
            assert 'invitation' in str(err)
        else:
            raise AssertionError('Expired invitation accepted')
        assert counter[0]==before_count
        checks.append(name+': invitation expiry checked inside real transaction')


        race_code=ipsk.create_invite('Fixture administrator')
        before_count=counter[0]
        def invite_race(number):
            try:
                return resident_access.create_device(ipsk,{**config,'invite_required':True},
                    identity('invite-'+str(number)),'TV','00:11:22:33:44:'+str(number),'',race_code,'192.0.2.1')
            except ValueError as err:
                return str(err)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(invite_race,[10,11]))
        assert sum(isinstance(r,dict) for r in results)==1,results
        assert counter[0]==before_count+1
        assert query('SELECT used_at FROM stepca_invites WHERE code_hash=SHA2(%s,256)',(race_code,))[0]['used_at'] is not None
        checks.append(name+': concurrent invitation consumption provisions one key')

        with ipsk.db_connect() as conn,conn.cursor() as cur:
            cur.execute("SET SESSION sql_mode=CONCAT(@@sql_mode,',PAD_CHAR_TO_FULL_LENGTH')")
            cur.execute('SELECT active_mac FROM stepca_resident_devices WHERE active_mac=%s',(first,))
            assert cur.fetchone()['active_mac']==first
        checks.append(name+': generated MAC index remains consistent across SQL padding modes')

        with patch.object(ipsk,'create_ipsk',return_value={'id':'invalid-remote','passphrase':'fixture-password'}):
            result=device('invalid','00:11:22:33:44:07')
        assert isinstance(result,str),result
        assert not query('SELECT id FROM stepca_resident_devices WHERE ipsk_id=%s',('invalid-remote',))
        assert ('invalid-remote','delete') in cleanup
        checks.append(name+': invalid authoritative credentials roll back and clean remote key')

    # Re-running startup with historical duplicates must not recreate obsolete indexes.
    db_setup.main()
    assert query('SELECT COUNT(*) AS n FROM stepca_resident_devices WHERE mac_address=%s',(first,))[0]['n']==2
    indexes=query("SHOW INDEX FROM stepca_resident_devices WHERE Key_name='uq_stepca_devices_mac'")
    assert not indexes,indexes
    checks.append(name+': repeated schema upgrade retains historical duplicates safely')
    check_inventory(name)


def check_inventory(name):
    """Exercise the complete UNION inventory with more than 250 fixture rows."""
    before = ipsk.resident_inventory()['total']
    with root_connect(name) as conn, conn.cursor() as cur:
        cur.executemany(
            'INSERT INTO stepca_residents (name,email,unit,ipsk_id,ipsk_name,created_at) '
            'VALUES (%s,%s,%s,%s,%s,%s)',
            [('Inventory Fixture %03d' % number, 'inventory-%d@example.org' % number,
              str(number), 'inventory-key-%d' % number, 'Inventory TV %03d' % number,
              datetime.datetime(2026, 1, 1) + datetime.timedelta(seconds=number))
             for number in range(300)])
        cur.execute('INSERT INTO stepca_resident_accounts (owner_key,name,email) VALUES (%s,%s,%s)',
                    ('inventory-owner', 'Inventory Fixture Account', 'inventory-account@example.org'))
        cur.executemany(
            'INSERT INTO stepca_resident_devices (owner_key,device_name,mac_address,ipsk_id,created_at) '
            'VALUES (%s,%s,%s,%s,%s)',
            [('inventory-owner', 'Inventory TV %d' % number, '00:22:33:44:55:%02x' % number,
              'inventory-account-key-%d' % number, datetime.datetime(2026, 1, 2))
             for number in range(3)])
    inventory = ipsk.resident_inventory('inventory fixture', 'name')
    assert inventory['total'] == before + 303, inventory
    assert inventory['matched'] == 303 and inventory['pages'] == 13
    seen = []
    for page in range(1, 14):
        part = ipsk.resident_inventory('inventory fixture', 'name', page)
        seen.extend((row['source'], row['record_id']) for row in part['rows'])
    assert len(seen) == len(set(seen)) == 303
    checks.append(name+': inventory pages all 303 matching legacy and account-device records without duplicates')
    filtered = ipsk.resident_inventory('inventory tv 299', 'oldest')
    assert filtered['matched'] == 1 and filtered['rows'][0]['ipsk_id'] == 'inventory-key-299'
    assert ipsk.resident_inventory("' OR 1=1 --")['matched'] == 0
    assert ipsk.resident_inventory('%')['matched'] == 0
    assert ipsk.resident_inventory('inventory fixture', 'invalid', 999999, 999)['page'] == 7
    assert len(ipsk.resident_inventory('inventory fixture', 'unit', 1, 999)['rows']) == 50
    assert ipsk.resident_inventory('inventory fixture', 'oldest', 1)['rows'][0]['ipsk_id'] == 'inventory-key-0'
    checks.append(name+': inventory searches all records with literal parameterized terms and bounded sorting/pagination')


if __name__=='__main__':
    # Wait for this disposable MariaDB process, not an assumed production service.
    for attempt in range(40):
        try:
            conn=root_connect()
            conn.close()
            break
        except pymysql.MySQLError:
            if attempt==39:
                raise
            time.sleep(.25)
    with root_connect() as conn,conn.cursor() as cur:
        cur.execute('SELECT VERSION() AS version')
        version=cur.fetchone()['version']
    for name in ('stepca_audit_fresh','stepca_audit_legacy'):
        run_schema(name)
    print(json.dumps({'mariadb':version,'checks':checks,'count':len(checks),'status':'passed'},indent=2))
