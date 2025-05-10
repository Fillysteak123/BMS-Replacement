# security.py

import os
import bcrypt

def verify_password(stored_hash, plain_password):
    """Compare stored hash against a plaintext password input."""
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode('utf-8')
    return bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash)

def validate_pdf(file_path):
    """Check if the file is a valid PDF (by header)."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            return header == b'%PDF'
    except Exception:
        return False

def secure_file_path(directory, filename):
    """Prevent directory traversal by ensuring path stays within base directory."""
    base = os.path.abspath(directory)
    target = os.path.abspath(os.path.join(base, filename))
    if not target.startswith(base):
        raise ValueError("Invalid file path: Potential directory traversal attempt")
    return target
