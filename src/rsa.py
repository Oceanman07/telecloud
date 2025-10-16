from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA


def generate_keys():
    keys = RSA.generate(2048)
    private_key = keys.export_key()
    public_key = keys.public_key().export_key()

    return private_key, public_key


def encrypt(public_key, data):
    cipher = PKCS1_OAEP.new(RSA.import_key(public_key))
    return cipher.encrypt(data)


def decrypt(private_key, encrypted_data):
    cipher = PKCS1_OAEP.new(RSA.import_key(private_key))
    return cipher.decrypt(encrypted_data)
