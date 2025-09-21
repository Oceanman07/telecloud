import os
import json
import base64

from .utils import read_file, write_file

STORED_CLOUDMAP_PATHS = os.path.join(os.path.expanduser('~'), '.telecloud')
CLOUDMAP_PATH = os.path.join(STORED_CLOUDMAP_PATHS, 'cloudmap.json')
SALT_PATH = os.path.join(STORED_CLOUDMAP_PATHS, 'salt')
INCLUDED_CLOUDMAP_PATHS = (STORED_CLOUDMAP_PATHS, CLOUDMAP_PATH, SALT_PATH)


def setup_cloudmap():
    os.makedirs(STORED_CLOUDMAP_PATHS, exist_ok=True)

    salt = os.urandom(32)
    write_file(SALT_PATH, base64.b64encode(salt).decode(), mode='w')

    cloudmap = {}
    write_file(CLOUDMAP_PATH, json.dumps(cloudmap), mode='w')

def check_health_cloudmap():
    return all(os.path.exists(path) for path in INCLUDED_CLOUDMAP_PATHS)

def update_cloudmap(cloudmap):
    write_file(CLOUDMAP_PATH, json.dumps(cloudmap, ensure_ascii=False), mode='w')

def get_cloudmap():
    return json.loads(read_file(CLOUDMAP_PATH))

def get_salt_from_cloudmap():
    salt = read_file(SALT_PATH)
    return base64.b64encode(salt)

def get_existed_file_paths_on_cloud():
    cloudmap = get_cloudmap()
    return [cloudmap[msg_id]['file_path'] for msg_id in cloudmap]

def get_existed_checksums():
    cloudmap = get_cloudmap()
    return [cloudmap[msg_id]['checksum'] for msg_id in cloudmap]
