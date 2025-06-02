"""Utilities for secure credential storage and retrieval."""
import base64
import getpass
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Salt for key derivation - in a real-world scenario, this should be stored securely
# This is a simplified implementation for demonstration purposes
SALT = b'thothforge_salt_for_credential_encryption'

# Cache for decryption passwords to avoid asking multiple times
_password_cache = {}


def _get_encryption_key(password: str) -> bytes:
    """
    Derive an encryption key from a password.
    
    :param password: Password to derive key from
    :return: Encryption key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_credentials(credentials: Dict[str, Any], password: str) -> bytes:
    """
    Encrypt credentials using a password.
    
    :param credentials: Dictionary of credentials to encrypt
    :param password: Password for encryption
    :return: Encrypted credentials as bytes
    """
    key = _get_encryption_key(password)
    fernet = Fernet(key)
    credentials_json = json.dumps(credentials).encode()
    encrypted_data = fernet.encrypt(credentials_json)
    return encrypted_data


def decrypt_credentials(encrypted_data: bytes, password: str) -> Dict[str, Any]:
    """
    Decrypt credentials using a password.
    
    :param encrypted_data: Encrypted credentials
    :param password: Password for decryption
    :return: Dictionary of decrypted credentials
    """
    key = _get_encryption_key(password)
    fernet = Fernet(key)
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
    except InvalidToken:
        logger.error("Invalid password or corrupted credential file")
        raise ValueError("Invalid password or corrupted credential file")


def save_credentials(
    space_name: str, 
    credentials: Dict[str, Any], 
    credential_type: str = "vcs",
    password: Optional[str] = None
) -> Path:
    """
    Save encrypted credentials to the space credentials directory.
    
    :param space_name: Name of the space
    :param credentials: Dictionary of credentials to save
    :param credential_type: Type of credentials (e.g., 'vcs', 'terraform')
    :param password: Password for encryption (will prompt if None)
    :return: Path to the saved credentials file
    """
    # Create credentials directory if it doesn't exist
    creds_dir = Path.home() / ".thothcf" / "spaces" / space_name / "credentials"
    os.makedirs(creds_dir, exist_ok=True)
    
    # Get password if not provided
    if password is None:
        password = getpass.getpass("Enter password to encrypt credentials: ")
    
    # Encrypt and save credentials
    encrypted_data = encrypt_credentials(credentials, password)
    creds_file = creds_dir / f"{credential_type}.enc"
    
    with open(creds_file, "wb") as f:
        f.write(encrypted_data)
    
    logger.info(f"Credentials saved to {creds_file}")
    return creds_file


def get_credentials_with_password(
    space_name: str,
    credential_type: str = "vcs"
) -> Tuple[Dict[str, Any], str]:
    """
    Load encrypted credentials and return both the credentials and the password used.
    
    :param space_name: Name of the space
    :param credential_type: Type of credentials (e.g., 'vcs', 'terraform')
    :return: Tuple of (credentials_dict, password_used)
    :raises: FileNotFoundError if credentials file doesn't exist
    :raises: ValueError if decryption fails
    """
    creds_file = Path.home() / ".thothcf" / "spaces" / space_name / "credentials" / f"{credential_type}.enc"
    
    if not creds_file.exists():
        logger.error(f"Credentials file not found: {creds_file}")
        raise FileNotFoundError(f"Credentials file not found: {creds_file}")
    
    # Check if we have a cached password for this space and credential type
    cache_key = f"{space_name}:{credential_type}"
    password = _password_cache.get(cache_key)
    
    # If no cached password, prompt for one
    if password is None:
        password = getpass.getpass("Enter password to decrypt credentials: ")
    
    # Read encrypted data
    with open(creds_file, "rb") as f:
        encrypted_data = f.read()
    
    try:
        # Try to decrypt with the password
        credentials = decrypt_credentials(encrypted_data, password)
        # Cache the successful password
        _password_cache[cache_key] = password
        return credentials, password
    except ValueError:
        # If decryption fails, prompt for a new password
        logger.warning("Failed to decrypt credentials, trying again with a new password")
        new_password = getpass.getpass("Invalid password. Enter the correct password: ")
        
        try:
            credentials = decrypt_credentials(encrypted_data, new_password)
            # Update the cache with the correct password
            _password_cache[cache_key] = new_password
            return credentials, new_password
        except ValueError:
            # If it fails again, clear the cache entry and re-raise
            if cache_key in _password_cache:
                del _password_cache[cache_key]
            raise


def load_credentials(
    space_name: str, 
    credential_type: str = "vcs",
    password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load encrypted credentials from the space credentials directory.
    
    :param space_name: Name of the space
    :param credential_type: Type of credentials (e.g., 'vcs', 'terraform')
    :param password: Password for decryption (will prompt if None)
    :return: Dictionary of decrypted credentials
    """
    # If password is provided, use it directly
    if password is not None:
        creds_file = Path.home() / ".thothcf" / "spaces" / space_name / "credentials" / f"{credential_type}.enc"
        
        if not creds_file.exists():
            logger.error(f"Credentials file not found: {creds_file}")
            raise FileNotFoundError(f"Credentials file not found: {creds_file}")
        
        with open(creds_file, "rb") as f:
            encrypted_data = f.read()
        
        try:
            return decrypt_credentials(encrypted_data, password)
        except ValueError:
            # If decryption fails, prompt for a new password
            logger.warning("Failed to decrypt credentials, trying again with a new password")
            new_password = getpass.getpass("Invalid password. Enter the correct password: ")
            return decrypt_credentials(encrypted_data, new_password)
    
    # Otherwise use the cached password or prompt for one
    credentials, _ = get_credentials_with_password(space_name, credential_type)
    return credentials


def validate_credentials(
    space_name: str,
    credential_type: str = "vcs",
    password: Optional[str] = None
) -> bool:
    """
    Validate that credentials can be decrypted.
    
    :param space_name: Name of the space
    :param credential_type: Type of credentials (e.g., 'vcs', 'terraform')
    :param password: Password for decryption (will prompt if None)
    :return: True if credentials are valid, False otherwise
    """
    try:
        if password is not None:
            load_credentials(space_name, credential_type, password)
        else:
            get_credentials_with_password(space_name, credential_type)
        return True
    except (FileNotFoundError, ValueError):
        return False
