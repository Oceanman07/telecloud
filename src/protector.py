from . import aes


def encrypt_file(key, file_path):
    with open(file_path, 'rb') as f:
        file_content = f.read()
    encrypted_data = aes.encrypt(key, file_content)

    with open(file_path + '.telecloud', 'wb') as f:
        f.write(encrypted_data)

def decrypt_file(key, file_path):
    with open(file_path , 'rb') as f:
        encrypted_data = f.read()
    original_data = aes.decrypt(key, encrypted_data)

    with open(file_path[:-10], 'wb') as f:
        f.write(original_data)

