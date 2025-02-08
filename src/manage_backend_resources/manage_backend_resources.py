"""Module import."""
import sys

import boto3
from colorama import Fore


def validate_backend(data) -> bool:
    """
    Check function for terraform backend files in the bucket.

    :param data: the data from the config file
    :return: True if there are no backend files, False if there are backend files.
    """
    path = data["path"].rstrip("/")
    session = boto3.session.Session(profile_name=f'{data["backend_profile"]}')
    s3_client = session.client("s3")
    resp = s3_client.list_objects(
        Bucket=data["bucket"], Prefix=path, Delimiter="/", MaxKeys=1
    )
    exist = "CommonPrefixes" in resp
    if not exist:
        print(Fore.GREEN)
        print("The project has no backend files.")
        print(Fore.RESET)
        return True
    else:
        sys.exit("The project already have backend files.")
