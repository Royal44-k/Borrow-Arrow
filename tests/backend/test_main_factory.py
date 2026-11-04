"""Importing the factory must not create a default production database."""
import os
import subprocess
import sys
from pathlib import Path

def test_factory_import_does_not_construct_default_services():
    backend=Path(__file__).resolve().parents[2]/'backend'
    code="""
from unittest.mock import patch
with patch('app.service.Courseware',side_effect=AssertionError('default course database opened')), patch('app.platform.Platform',side_effect=AssertionError('default platform database opened')):
    from app.main import create_app
    assert callable(create_app)
"""
    result=subprocess.run([sys.executable,'-c',code],cwd=backend,env={**os.environ,'PYTHONPATH':str(backend)},capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
