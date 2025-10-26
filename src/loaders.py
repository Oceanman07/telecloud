import os

from telethon.sessions import StringSession

from . import aes, rsa
from .utils import read_file
from .constants import STRING_SESSION_PATH, ENCRYPTED_PRIVATE_KEY_PATH
from .config_manager.config_loader import get_encrypted_symmetric_key


def load_string_session(symmetric_key):
    encrypted_session = read_file(STRING_SESSION_PATH)
    session = aes.decrypt(symmetric_key, encrypted_session)

    return StringSession(session.decode())


def load_symmetric_key(password):
    with open(ENCRYPTED_PRIVATE_KEY_PATH, "rb") as f:
        salt = f.read(32)
        encrypted_private_key = f.read()

    symmetric_key_for_private_key = aes.generate_key(password, salt)
    try:
        private_key = aes.decrypt(symmetric_key_for_private_key, encrypted_private_key)
    except ValueError:
        return {"success": False, "error": "Invalid password"}

    encrypted_main_symmetric_key = bytes.fromhex(get_encrypted_symmetric_key())
    main_symmetric_key = rsa.decrypt(private_key, encrypted_main_symmetric_key)
    return {"success": True, "symmetric_key": main_symmetric_key}
