import os

STORED_CLOUDMAP_PATHS = os.path.join(os.path.expanduser('~'), '.telecloud')
SESSION_PATH = os.path.join(STORED_CLOUDMAP_PATHS, 'session')
SALT_PATH = os.path.join(STORED_CLOUDMAP_PATHS, 'salt')
CLOUDMAP_PATH = os.path.join(STORED_CLOUDMAP_PATHS, 'cloudmap.json')
INCLUDED_CLOUDMAP_PATHS = (STORED_CLOUDMAP_PATHS, CLOUDMAP_PATH, SALT_PATH)

EXT_IDENTIFIER = '.telecloud'
