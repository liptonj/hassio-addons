"""Check a disposable running Step CA image; never target a deployed CA.

Run as user step inside the isolated startup fixture container. The assertions
below require the audit database and root name before issuing any certificate.
No private key, PKCS#12 password or CA credential is printed.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, '/opt/step-ca-admin')
import enroll
import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509

root='/data/step/certs/root_ca.crt'
url='https://localhost:9000'
config=json.loads(Path('/data/step/config/ca.json').read_text())
root_cert=x509.load_pem_x509_certificate(Path(root).read_bytes())
assert config['db']['type']=='mysql' and config['db']['database']=='stepca_audit_startup'
assert 'Isolated Step CA audit' in root_cert.subject.rfc4514_string()
assert 'stepca-audit-addon' in config['dnsNames']
bundle,password,leaf=enroll.issue_p12('Isolated audit device',ca_url=url,root_cert=root,
                                     sans=['audit-device.example.org'],not_after='1h')
key,cert,chain=pkcs12.load_key_and_certificates(bundle,password.encode())
assert key and cert.serial_number==leaf.serial_number and len(chain)>=2
checks=['full startup with one MariaDB-backed CA','real CSR signing and decryptable PKCS#12 chain']
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)
    certfile=path/'cert.pem'
    keyfile=path/'key.pem'
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
    renewed=subprocess.run(['step','ca','renew',str(certfile),str(keyfile),'--ca-url',url,'--root',root,'--force'],
                           capture_output=True,text=True,timeout=30)
    assert renewed.returncode==0,renewed.stderr
    renewed_cert=x509.load_pem_x509_certificate(certfile.read_bytes())
    assert renewed_cert.serial_number!=cert.serial_number
    checks.append('actual certificate renewal with existing device key')
    error=app.revoke(str(renewed_cert.serial_number),4,'Isolated audit fixture')
    assert error is None,error
    checks.append('actual certificate revocation')
    crl=subprocess.run(['curl','--silent','--fail','http://127.0.0.1:9080/crl'],capture_output=True,
                       timeout=10,check=True).stdout
    parsed=x509.load_der_x509_crl(crl)
    assert parsed.get_revoked_certificate_by_serial_number(renewed_cert.serial_number) is not None
    checks.append('published CRL contains revoked certificate')
caps=subprocess.run(['curl','--silent','--fail','http://127.0.0.1:9080/scep/scep?operation=GetCACaps'],
                    capture_output=True,timeout=10,check=True).stdout
assert b'POSTPKIOperation' in caps and b'SHA-256' in caps
checks.append('running SCEP provisioner advertises supported capabilities')
manifest=json.loads(Path('/homeassistant/custom_components/step_ca_scep/manifest.json').read_text())
assert manifest['version']=='1.5.2'
assert Path('/homeassistant/custom_components/step_ca_scep/ipsk_websocket.py').is_file()
checks.append('companion integration 1.5.2 installed with iPSK bridge')
print(json.dumps({'status':'passed','checks':checks,'count':len(checks),
                  'certificate_material':'disposable fixture only'},indent=2))
