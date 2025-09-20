import hashlib

from . import aes


def encrypt_file(key, file_name_hash, file_path):
    with open(file_path, 'rb') as f:
        file_content = f.read()
    encrypted_data = aes.encrypt(key, file_content)

    file_name_hash['file_name_hash'] = hashlib.sha1(file_path.encode()).hexdigest()
    with open(file_name_hash['file_name_hash'], 'wb') as f:
        f.write(encrypted_data)

def decrypt_file(key, file_name_hash, file_path):
    with open(file_name_hash, 'rb') as f:
        encrypted_data = f.read()
    original_data = aes.decrypt(key, encrypted_data)

    with open(file_path, 'wb') as f:
        f.write(original_data)

