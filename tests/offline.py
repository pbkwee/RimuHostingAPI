"""Keep tests self-contained and prevent real network access."""
from pathlib import Path
import socket
import os
import sys

if not __debug__:
    raise RuntimeError("Run the offline tests without Python optimization; they use assertions.")

sys.dont_write_bytecode = True
# Do not inherit a real output directory into mocked command runs.
os.environ['RIMUHOSTING_LOGDIR'] = ''
os.environ['RIMUHOSTING_OUTPUT'] = 'json'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def deny_network(*args, **kwargs):
    raise AssertionError("Network access is disabled in offline tests; mock the HTTP transport.")


socket.getaddrinfo = deny_network
socket.create_connection = deny_network
socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
