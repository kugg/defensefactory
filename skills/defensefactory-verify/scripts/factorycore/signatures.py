"""Verifier receipt authentication. Trusted key distribution is an external policy boundary."""
import base64
from pathlib import Path
import subprocess
import tempfile
from .core import canonical, require, sha


def sign(receipt, private_key):
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'receipt';p.write_bytes(canonical(receipt))
        signature=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(private_key),str(p)],stderr=subprocess.PIPE)
    return {'receipt':receipt,'signature':base64.b64encode(signature).decode()}


def verify_signed(envelope, public_key_pem, *, expected_actor, expected_subject):
    receipt=envelope['receipt']
    require(receipt.get('actor')==expected_actor and receipt.get('subject')==expected_subject, 'Signed receipt actor/subject mismatch')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'key').write_text(public_key_pem);(root/'receipt').write_bytes(canonical(receipt));(root/'sig').write_bytes(base64.b64decode(envelope['signature'],validate=True))
        p=subprocess.run(['openssl','dgst','-sha256','-verify',str(root/'key'),'-signature',str(root/'sig'),str(root/'receipt')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    require(p.returncode==0, 'Invalid verifier signature')
    return {'receipt':receipt,'public_key_sha256':sha(public_key_pem.encode()),'note':'Signature authenticates this configured key; OS/credential isolation and policy trust must be separately established.'}
