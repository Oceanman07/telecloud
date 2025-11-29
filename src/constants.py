import os
import datetime


_HOME_DIR = os.path.expanduser("~")

PULLED_DIR_IN_DESKTOP = os.path.join(
    _HOME_DIR, os.path.join("Desktop", "TeleCloudFiles")
)
PULLED_DIR_IN_DOCUMENTS = os.path.join(
    _HOME_DIR, os.path.join("Documents", "TeleCloudFiles")
)
PULLED_DIR_IN_DOWNLOADS = os.path.join(
    _HOME_DIR, os.path.join("Downloads", "TeleCloudFiles")
)

STORED_CLOUDMAP_PATHS = os.path.join(_HOME_DIR, ".telecloud")
PUBLIC_KEY_PATH = os.path.join(STORED_CLOUDMAP_PATHS, "public_key.pem")
ENCRYPTED_PRIVATE_KEY_PATH = os.path.join(
    STORED_CLOUDMAP_PATHS, "encrypted_private_key.pem"
)
CONFIG_PATH = os.path.join(STORED_CLOUDMAP_PATHS, "config.json")
CACHE_PATH = os.path.join(STORED_CLOUDMAP_PATHS, "cache")
CURRENT_TIMESTAMP = str(datetime.datetime.now().timestamp())
PREPARED_DATA_CACHE_PATH = os.path.join(CACHE_PATH, CURRENT_TIMESTAMP)
STRING_SESSION_PATH = os.path.join(STORED_CLOUDMAP_PATHS, "StringSession")
CLOUDMAP_DB_PATH = os.path.join(STORED_CLOUDMAP_PATHS, "cloudmap.db")
INCLUDED_CLOUDMAP_PATHS = (STORED_CLOUDMAP_PATHS, CLOUDMAP_DB_PATH)

NAMING_FILE_MAX_LENGTH = 255
NONCE_LENGTH = 12
TAG_LENGTH = 16
CHUNK_LENGTH_FOR_LARGE_FILE = 7 * 1024 * 1024  # 7MB
