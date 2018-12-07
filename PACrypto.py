#!/usr/bin/env python3
import random
import base64
import cryptography.hazmat.backends
import cryptography.hazmat.primitives
import cryptography.hazmat.primitives.asymmetric.ec
import cryptography.hazmat.primitives.hashes


def generate_private_key():
    pkey = cryptography.hazmat.primitives.asymmetric.ec.generate_private_key(
        cryptography.hazmat.primitives.asymmetric.ec.SECP256K1(), cryptography.hazmat.backends.default_backend())
    pkey_hex = '{:0>64x}'.format(pkey.private_numbers().private_value)
    return pkey_hex


def generate_public_key(pkey_hex):
    pkey = cryptography.hazmat.primitives.asymmetric.ec.derive_private_key(
        int(pkey_hex, base=16), cryptography.hazmat.primitives.asymmetric.ec.SECP256K1(), cryptography.hazmat.backends.default_backend())
    pubkey = pkey.public_key()
    pubkey_hex_x = '{:0>64x}'.format(pubkey.public_numbers().x)
    pubkey_hex_y = '{:0>64x}'.format(pubkey.public_numbers().y)
    pubkey_hex = pubkey_hex_x + pubkey_hex_y
    return pubkey_hex


def generate_address(pubkey_hex):
    pubkey_bytes = int(pubkey_hex, base=16).to_bytes(64, byteorder='big')
    hash_engine = cryptography.hazmat.primitives.hashes.Hash(
        cryptography.hazmat.primitives.hashes.SHA512(), cryptography.hazmat.backends.default_backend())
    hash_engine.update(int(pubkey_hex, base=16).to_bytes(64, byteorder='big'))
    pubkey_hash = hash_engine.finalize()
    pubkey_hash_base64 = base64.b64encode(pubkey_hash)
#    pubkey_hash = int.from_bytes(pubkey_hash, byteorder='big')
#    print('{:x}'.format(pubkey_hash))
    return pubkey_hash_base64


def generate_address(pubkey_hex):
    pubkey_bytes = int(pubkey_hex, base=16).to_bytes(64, byteorder='big')
    hash_engine = cryptography.hazmat.primitives.hashes.Hash(
        cryptography.hazmat.primitives.hashes.SHA512(), cryptography.hazmat.backends.default_backend())
    hash_engine.update(int(pubkey_hex, base=16).to_bytes(64, byteorder='big'))
    pubkey_hash = hash_engine.finalize()
    pubkey_hash_base64 = base64.b64encode(pubkey_hash)
#    pubkey_hash = int.from_bytes(pubkey_hash, byteorder='big')
#    print('{:x}'.format(pubkey_hash))
    return pubkey_hash_base64.decode("utf-8")


def verify_address(address, pubkey_hex):
    try:
        address_gen = generate_address(pubkey_hex)
        assert address_gen == address
        return True
    except Exception as e:
        return False


def generate_sign(data, pkey_hex):
    pkey = cryptography.hazmat.primitives.asymmetric.ec.derive_private_key(
        int(pkey_hex, base=16), cryptography.hazmat.primitives.asymmetric.ec.SECP256K1(), cryptography.hazmat.backends.default_backend())
    sign = pkey.sign(data, cryptography.hazmat.primitives.asymmetric.ec.ECDSA(
        cryptography.hazmat.primitives.hashes.SHA512()))
    return base64.b64encode(sign)


def verify_sign(data, sign, pubkey_hex):
    try:
        sign = base64.b64decode(sign)
        pubkey = cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePublicNumbers(int(pubkey_hex[:64], base=16), int(
            pubkey_hex[64:], base=16), cryptography.hazmat.primitives.asymmetric.ec.SECP256K1()).public_key(cryptography.hazmat.backends.default_backend())
        pubkey.verify(sign, data, cryptography.hazmat.primitives.asymmetric.ec.ECDSA(
            cryptography.hazmat.primitives.hashes.SHA512()))
        return True
    except Exception as e:
        return False


def generate_hash(data):
    hash_engine = cryptography.hazmat.primitives.hashes.Hash(
        cryptography.hazmat.primitives.hashes.SHA512(), cryptography.hazmat.backends.default_backend())
    hash_engine.update(data)
    return '{:0>128x}'.format(int.from_bytes(hash_engine.finalize(), byteorder='big'))


# pkey = cryptography.hazmat.primitives.asymmetric.ec.derive_private_key(int(pkey_hex, base=16), cryptography.hazmat.primitives.asymmetric.ec.SECP256K1(), cryptography.hazmat.backends.default_backend())
# assert pkey_hex == '{:x}'.format(pkey.private_numbers().private_value)
#
# pubkey = cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePublicNumbers(int(pubkey_hex[:64], base=16), int(pubkey_hex[64:], base=16), cryptography.hazmat.primitives.asymmetric.ec.SECP256K1()).public_key(cryptography.hazmat.backends.default_backend())
# assert pubkey_hex_x == '{:x}'.format(pubkey.public_numbers().x)
# assert pubkey_hex_y == '{:x}'.format(pubkey.public_numbers().y)

# print(pubkey_hex)
# pubkey_bytes=int(pubkey_hex, base=16).to_bytes(64, byteorder='big')
# hash_engine = cryptography.hazmat.primitives.hashes.Hash(cryptography.hazmat.primitives.hashes.SHA512(), cryptography.hazmat.backends.default_backend())
# hash_engine.update(int(pubkey_hex, base=16).to_bytes(64, byteorder='big'))
# pubkey_hash = hash_engine.finalize()
# pubkey_hash = int.from_bytes(pubkey_hash, byteorder='big')
# print('{:x}'.format(pubkey_hash))

# pkey = generate_private_key()
# pubkey = generate_public_key(pkey)
# addr = generate_address(pubkey)
# print(verify_address(addr, pubkey))
# print(verify_address("asdasadasdasd", pubkey))
# data = b"1234567890"
# sign = generate_sign(data, pkey)
# print(verify_sign(data, sign, pubkey))
# print(verify_sign("12312312", sign, pubkey))
