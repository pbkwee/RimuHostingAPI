"""Check CLI request methods, routes and payloads with real preparation and mocked HTTP."""
from offline import ROOT

import contextlib
import io
import json
import os
import runpy
import sys
from unittest.mock import patch

import requests
import rimuapi


with patch.object(rimuapi, 'load_settings', return_value=None), \
        patch.dict(os.environ, {'RIMUHOSTING_BASEURL': 'https://example.invalid'}):
    api = rimuapi.Api(key='offline-request-key')

vm = '/r/orders/order-123456-na.com'
cases = [
    ('vmctl.py', ['start'], 'PUT', vm + '/vps/running-state',
     {'running_state_change_request': {'running_state': 'RUNNING'}}, 'put_running_state_response'),
    ('vmctl.py', ['stop'], 'PUT', vm + '/vps/running-state',
     {'running_state_change_request': {'running_state': 'NOTRUNNING'}}, 'put_running_state_response'),
    ('vmctl.py', ['restart'], 'PUT', vm + '/vps/running-state',
     {'running_state_change_request': {'running_state': 'RESTARTING'}}, 'put_running_state_response'),
    ('vmctl.py', ['status'], 'GET', vm + '/vps', None, 'get_vps_status_response'),
    ('vmctl.py', ['info'], 'GET', vm, None, 'get_order_response'),
    ('rmvm.py', [], 'DELETE', vm + '/vps', None, 'delete_server_response'),
    # The resource command passes no domain; the server identifies the VM by order ID.
    ('chattrvm.py', ['--memory_mb', '512'], 'PUT', '/r/orders/order-123456-None/vps/parameters',
     {'running_vps_data': {'memory_mb': 512}}, 'put_running_vps_data_response'),
    ('chattrvm.py', ['--disk_space_2_gb', '0'], 'PUT', '/r/orders/order-123456-None/vps/parameters',
     {'running_vps_data': {'disk_space_2_mb': 0}}, 'put_running_vps_data_response'),
    ('rdns.py', ['--ip', '192.0.2.10', '--domain_name', 'vm+label example.test'], 'PUT',
     '/r/orders/order-123456-example.com/ptr;ip=192.0.2.10',
     'domain_name=vm%2Blabel+example.test', 'jaxrs_response'),
    ('rdns.py', ['--ip', '192.0.2.10', '--domain_name', ''], 'PUT',
     '/r/orders/order-123456-example.com/ptr;ip=192.0.2.10', 'domain_name=', 'jaxrs_response'),
    ('rdns.py', [], 'PUT', '/r/orders/order-123456-example.com/ptr;ip=',
     'domain_name=', 'jaxrs_response'),
]

for script, arguments, method, path, payload, wrapper in cases:
    response = requests.Response()
    response.status_code, response.reason = 200, 'OK'
    response.headers['content-type'] = 'application/json'
    response._content = json.dumps({wrapper: {'human_readable_message': 'Offline fixture result'}}).encode()
    # Disable environment/netrc lookup; only synthetic credentials enter the real request preparation.
    with requests.Session() as session:
        session.trust_env = False
        with patch.object(rimuapi, 'load_settings', return_value=None), \
                patch.object(session, 'send', return_value=response) as send, \
                patch.object(rimuapi, 'Session', return_value=session), \
                patch.object(rimuapi, 'Api', return_value=api), \
                patch.object(sys, 'argv', [script, '--order_oid', '123456', *arguments]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            runpy.run_path(str(ROOT / script), run_name='__main__')

        assert send.call_count == 1, (script, 'Unexpected lookup or retry')
        prepared = send.call_args.args[0]
        assert isinstance(prepared, requests.PreparedRequest)
        assert prepared.method == method, (script, prepared.method)
        assert prepared.url == 'https://example.invalid' + path, (script, prepared.url)
        assert prepared.headers['Authorization'] == 'rimuhosting apikey=offline-request-key'
        assert prepared.headers['Accept'] == 'application/json'
        if isinstance(payload, str):
            assert prepared.headers['Content-Type'] == 'application/x-www-form-urlencoded'
            assert prepared.body == payload, (script, prepared.body)
        else:
            assert prepared.headers['Content-Type'] == 'application/json'
            assert json.loads(prepared.body) == payload, (script, prepared.body)
        assert send.call_args.kwargs == {'timeout': (30, 3600), 'verify': True}
        assert 'Offline fixture result' in output.getvalue()

print('CLI request contract checks passed (no live API calls).')
