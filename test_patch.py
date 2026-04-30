#!/usr/bin/env python3
"""Test the security patch"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# First apply the patch
from cms_project.security_patch import *

# Now try to simulate the problematic ForeignKey
from django.db import models

# Simulate what security.models does
USER_MODEL = 'auth.User'

try:
    # This should fail without patch, work with patch
    field = models.ForeignKey(USER_MODEL, unique=True)
    print("SUCCESS: ForeignKey created with patch")
    print(f"Field on_delete: {field.on_delete}")
except TypeError as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()