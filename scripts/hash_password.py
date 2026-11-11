#!/usr/bin/env python3
"""
DEVELOPMENT SCRIPT ONLY
Utility script to generate password hashes.
WARNING: Never use this in production environments.
"""

import os
import bcrypt

# Generate hash for password - use environment variable with safe default
password = os.getenv("HASH_PASSWORD", "secret")
print(f"Generating hash for password: {'***' if password else 'default'}")

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(f"Hash: {hashed.decode('utf-8')}")

# Test the hash
result = bcrypt.checkpw(password.encode('utf-8'), hashed)
print(f"Verification result: {result}")