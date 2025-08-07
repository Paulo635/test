"""
Cryptography utilities for OpenBullet Python
Provides encryption/decryption for sensitive data like configs and wordlists
"""

import os
import base64
import hashlib
import hmac
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import secrets
import logging

class CryptoManager:
    """
    Advanced cryptography manager for OpenBullet Python
    Handles encryption/decryption of sensitive data with multiple algorithms
    """
    
    def __init__(self, master_password: Optional[str] = None):
        self.master_password = master_password
        self.salt = None
        self.key = None
        self.fernet = None
        
        # Initialize if master password provided
        if master_password:
            self.initialize_crypto(master_password)
            
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def initialize_crypto(self, master_password: str, salt: Optional[bytes] = None):
        """Initialize cryptographic components with master password"""
        self.master_password = master_password
        
        # Generate or use provided salt
        if salt is None:
            self.salt = os.urandom(32)
        else:
            self.salt = salt
            
        # Derive key from password
        self.key = self._derive_key(master_password, self.salt)
        
        # Initialize Fernet cipher
        fernet_key = base64.urlsafe_b64encode(self.key[:32])
        self.fernet = Fernet(fernet_key)
        
        self.logger.info("Cryptographic components initialized")
        
    def _derive_key(self, password: str, salt: bytes, iterations: int = 100000) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
        
    def encrypt_string(self, plaintext: str) -> str:
        """Encrypt a string and return base64 encoded result"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        encrypted = self.fernet.encrypt(plaintext.encode())
        return base64.b64encode(encrypted).decode()
        
    def decrypt_string(self, ciphertext: str) -> str:
        """Decrypt a base64 encoded string"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        try:
            encrypted_data = base64.b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(encrypted_data)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
            
    def encrypt_file(self, input_path: str, output_path: str) -> bool:
        """Encrypt a file"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        try:
            with open(input_path, 'rb') as infile:
                data = infile.read()
                
            encrypted_data = self.fernet.encrypt(data)
            
            with open(output_path, 'wb') as outfile:
                # Write salt first, then encrypted data
                outfile.write(len(self.salt).to_bytes(4, 'big'))
                outfile.write(self.salt)
                outfile.write(encrypted_data)
                
            self.logger.info(f"File encrypted: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"File encryption failed: {e}")
            return False
            
    def decrypt_file(self, input_path: str, output_path: str, password: str) -> bool:
        """Decrypt a file"""
        try:
            with open(input_path, 'rb') as infile:
                # Read salt length
                salt_length = int.from_bytes(infile.read(4), 'big')
                
                # Read salt
                salt = infile.read(salt_length)
                
                # Read encrypted data
                encrypted_data = infile.read()
                
            # Initialize crypto with the salt
            self.initialize_crypto(password, salt)
            
            # Decrypt data
            decrypted_data = self.fernet.decrypt(encrypted_data)
            
            with open(output_path, 'wb') as outfile:
                outfile.write(decrypted_data)
                
            self.logger.info(f"File decrypted: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"File decryption failed: {e}")
            return False
            
    def encrypt_config(self, config_data: Dict[str, Any]) -> str:
        """Encrypt configuration data"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        # Convert to JSON and encrypt
        json_data = json.dumps(config_data, indent=2)
        return self.encrypt_string(json_data)
        
    def decrypt_config(self, encrypted_config: str) -> Dict[str, Any]:
        """Decrypt configuration data"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        # Decrypt and parse JSON
        json_data = self.decrypt_string(encrypted_config)
        return json.loads(json_data)
        
    def encrypt_wordlist(self, wordlist: List[str]) -> str:
        """Encrypt wordlist data"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        # Join wordlist and encrypt
        wordlist_data = '\n'.join(wordlist)
        return self.encrypt_string(wordlist_data)
        
    def decrypt_wordlist(self, encrypted_wordlist: str) -> List[str]:
        """Decrypt wordlist data"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        # Decrypt and split lines
        wordlist_data = self.decrypt_string(encrypted_wordlist)
        return [line.strip() for line in wordlist_data.split('\n') if line.strip()]
        
    def generate_secure_key(self, length: int = 32) -> str:
        """Generate a secure random key"""
        return base64.b64encode(os.urandom(length)).decode()
        
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """Hash a password with salt"""
        if salt is None:
            salt = os.urandom(32)
            
        # Use PBKDF2 for password hashing
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        
        # Return hash and salt as base64
        return (
            base64.b64encode(key).decode(),
            base64.b64encode(salt).decode()
        )
        
    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """Verify a password against its hash"""
        try:
            # Decode salt
            salt_bytes = base64.b64decode(salt.encode())
            
            # Hash the provided password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=100000,
                backend=default_backend()
            )
            
            key = kdf.derive(password.encode())
            computed_hash = base64.b64encode(key).decode()
            
            # Compare hashes
            return hmac.compare_digest(hashed_password, computed_hash)
            
        except Exception:
            return False
            
    def create_secure_container(self, data: Dict[str, Any], 
                               container_path: str) -> bool:
        """Create an encrypted container file"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        try:
            # Create container metadata
            container = {
                'version': '1.0',
                'created_at': self._get_timestamp(),
                'data_hash': self._calculate_hash(json.dumps(data)),
                'data': data
            }
            
            # Encrypt container
            container_json = json.dumps(container, indent=2)
            encrypted_container = self.encrypt_string(container_json)
            
            # Save to file
            with open(container_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_container)
                
            self.logger.info(f"Secure container created: {container_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create secure container: {e}")
            return False
            
    def load_secure_container(self, container_path: str, 
                             verify_integrity: bool = True) -> Optional[Dict[str, Any]]:
        """Load and decrypt a secure container"""
        if not self.fernet:
            raise ValueError("Crypto not initialized. Call initialize_crypto first.")
            
        try:
            # Read encrypted container
            with open(container_path, 'r', encoding='utf-8') as f:
                encrypted_container = f.read()
                
            # Decrypt container
            container_json = self.decrypt_string(encrypted_container)
            container = json.loads(container_json)
            
            # Verify integrity if requested
            if verify_integrity:
                expected_hash = container.get('data_hash', '')
                actual_hash = self._calculate_hash(json.dumps(container['data']))
                
                if not hmac.compare_digest(expected_hash, actual_hash):
                    raise ValueError("Container integrity check failed")
                    
            self.logger.info(f"Secure container loaded: {container_path}")
            return container['data']
            
        except Exception as e:
            self.logger.error(f"Failed to load secure container: {e}")
            return None
            
    def encrypt_proxy_list(self, proxies: List[str]) -> str:
        """Encrypt proxy list"""
        return self.encrypt_string('\n'.join(proxies))
        
    def decrypt_proxy_list(self, encrypted_proxies: str) -> List[str]:
        """Decrypt proxy list"""
        decrypted = self.decrypt_string(encrypted_proxies)
        return [proxy.strip() for proxy in decrypted.split('\n') if proxy.strip()]
        
    def secure_delete_file(self, file_path: str, passes: int = 3) -> bool:
        """Securely delete a file by overwriting it"""
        try:
            path = Path(file_path)
            if not path.exists():
                return True
                
            file_size = path.stat().st_size
            
            with open(file_path, 'r+b') as f:
                for _ in range(passes):
                    # Overwrite with random data
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
                    
            # Finally delete the file
            path.unlink()
            
            self.logger.info(f"File securely deleted: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Secure file deletion failed: {e}")
            return False
            
    def generate_session_token(self, data: Dict[str, Any], 
                              expiry_minutes: int = 60) -> str:
        """Generate a secure session token"""
        import time
        
        # Add expiry timestamp
        token_data = data.copy()
        token_data['expires_at'] = time.time() + (expiry_minutes * 60)
        
        # Encrypt the token data
        return self.encrypt_string(json.dumps(token_data))
        
    def verify_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a session token"""
        import time
        
        try:
            # Decrypt token
            token_json = self.decrypt_string(token)
            token_data = json.loads(token_json)
            
            # Check expiry
            if time.time() > token_data.get('expires_at', 0):
                return None
                
            # Remove expiry from returned data
            token_data.pop('expires_at', None)
            return token_data
            
        except Exception:
            return None
            
    def encrypt_api_key(self, api_key: str, service_name: str) -> str:
        """Encrypt an API key with service context"""
        data = {
            'api_key': api_key,
            'service': service_name,
            'created_at': self._get_timestamp()
        }
        return self.encrypt_string(json.dumps(data))
        
    def decrypt_api_key(self, encrypted_key: str) -> Tuple[str, str]:
        """Decrypt an API key and return key and service name"""
        data_json = self.decrypt_string(encrypted_key)
        data = json.loads(data_json)
        return data['api_key'], data['service']
        
    def create_backup_key(self, password: str) -> Tuple[str, str]:
        """Create a backup key for recovery purposes"""
        # Generate a secure backup key
        backup_key = self.generate_secure_key(64)
        
        # Encrypt the backup key with the password
        backup_fernet = Fernet(base64.urlsafe_b64encode(self._derive_key(password, b'backup_salt')[:32]))
        encrypted_backup = backup_fernet.encrypt(backup_key.encode())
        
        return backup_key, base64.b64encode(encrypted_backup).decode()
        
    def restore_from_backup(self, backup_key: str, encrypted_backup: str, 
                           password: str) -> bool:
        """Restore crypto from backup key"""
        try:
            # Decrypt backup key
            backup_fernet = Fernet(base64.urlsafe_b64encode(self._derive_key(password, b'backup_salt')[:32]))
            encrypted_data = base64.b64decode(encrypted_backup.encode())
            decrypted_backup = backup_fernet.decrypt(encrypted_data).decode()
            
            # Verify backup key matches
            if not hmac.compare_digest(backup_key, decrypted_backup):
                return False
                
            # Reinitialize crypto with original password
            self.initialize_crypto(password)
            return True
            
        except Exception as e:
            self.logger.error(f"Backup restoration failed: {e}")
            return False
            
    def _calculate_hash(self, data: str) -> str:
        """Calculate SHA-256 hash of data"""
        return hashlib.sha256(data.encode()).hexdigest()
        
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
        
    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Change the master password"""
        try:
            # Verify old password
            if self.master_password != old_password:
                return False
                
            # Re-initialize with new password
            self.initialize_crypto(new_password)
            return True
            
        except Exception as e:
            self.logger.error(f"Password change failed: {e}")
            return False
            
    def get_crypto_info(self) -> Dict[str, Any]:
        """Get information about current crypto setup"""
        return {
            'initialized': self.fernet is not None,
            'has_master_password': self.master_password is not None,
            'salt_length': len(self.salt) if self.salt else 0,
            'algorithm': 'Fernet (AES 128)',
            'key_derivation': 'PBKDF2-HMAC-SHA256'
        }
        
    def export_encrypted_data(self, data: Any, output_path: str) -> bool:
        """Export any data in encrypted format"""
        try:
            # Convert data to JSON if not string
            if isinstance(data, str):
                data_str = data
            else:
                data_str = json.dumps(data, indent=2)
                
            # Encrypt and save
            encrypted_data = self.encrypt_string(data_str)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
                
            self.logger.info(f"Encrypted data exported to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Data export failed: {e}")
            return False
            
    def import_encrypted_data(self, input_path: str) -> Any:
        """Import encrypted data"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()
                
            # Decrypt data
            decrypted_data = self.decrypt_string(encrypted_data)
            
            # Try to parse as JSON, return as string if fails
            try:
                return json.loads(decrypted_data)
            except json.JSONDecodeError:
                return decrypted_data
                
        except Exception as e:
            self.logger.error(f"Data import failed: {e}")
            return None

# Utility functions
def generate_random_password(length: int = 16) -> str:
    """Generate a random password"""
    import string
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(chars) for _ in range(length))

def is_password_strong(password: str) -> Tuple[bool, List[str]]:
    """Check if password meets strength requirements"""
    issues = []
    
    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")
        
    if not any(c.isupper() for c in password):
        issues.append("Password must contain at least one uppercase letter")
        
    if not any(c.islower() for c in password):
        issues.append("Password must contain at least one lowercase letter")
        
    if not any(c.isdigit() for c in password):
        issues.append("Password must contain at least one digit")
        
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        issues.append("Password must contain at least one special character")
        
    return len(issues) == 0, issues