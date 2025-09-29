from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes


def generate_key(password, salt):
    return PBKDF2(password, salt, dkLen=32, count=600000, hmac_hash_module=SHA256)


def encrypt(key, data):
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce)
    cipher_data, tag = cipher.encrypt_and_digest(data)
    return nonce + tag + cipher_data


def decrypt(key, encrypted_data):
    nonce, tag, cipher_data = (
        encrypted_data[:12],
        encrypted_data[12 : 12 + 16],
        encrypted_data[12 + 16 :],
    )
    cipher = AES.new(key, AES.MODE_GCM, nonce)
    original_data = cipher.decrypt_and_verify(cipher_data, tag)
    return original_data
