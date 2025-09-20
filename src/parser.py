import argparse


def parse_args():
    args = argparse.ArgumentParser()

    args.add_argument('--push', dest='push', action='store_true',
        help="Upload data to Telegram's cloud")

    args.add_argument('--pull', dest='pull', action='store_true',
        help="Retrive data from Telegram's cloud")

    args.add_argument('-d', '--directory', dest='directory',
        help='Directory path to upload/retrieve files')

    args.add_argument('-p', '--password', dest='password',
        help='Password for encryption/decryption')

    return args.parse_args()

