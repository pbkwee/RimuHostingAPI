"""Create, reinstall and quote clone requests using mocked HTTP only."""
from offline import ROOT

import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import patch

import requests
import rimuapi


def run(arguments, script='mkvm.py', failure=False):
    calls = []

    def respond(prepared, **options):
        calls.append(prepared)
        assert options == dict(timeout=(30, 3600), verify=True,
                               **({'stream': True} if '--progress' in arguments else {}))
        response = requests.Response()
        response.status_code, response.reason = (406, 'Not Acceptable') if failure else (200, 'OK')
        response.headers['content-type'] = 'application/json'
        if prepared.method == 'GET':
            body = {'get_orders_response': {'about_orders': [{'order_oid': 654321}]}}
        else:
            wrapper = 'get_new_vm_pricing_response' if script == 'pricing.py' else 'post_new_vps_response'
            body = {wrapper: {'human_readable_message': 'Offline result'}}
        response._content = json.dumps(body).encode()
        response._content_consumed = True
        return response

    with requests.Session() as session:
        session.trust_env = False
        with patch.object(rimuapi, 'load_settings', return_value=None), \
                patch.dict(os.environ, {'RIMUHOSTING_BASEURL': 'https://example.invalid',
                                        'RIMUHOSTING_APIKEY': 'offline-key'}), \
                patch.object(rimuapi, 'Session', return_value=session), \
                patch.object(session, 'send', side_effect=respond), \
                patch.object(sys, 'argv', [script, *arguments]), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = 0
            try:
                runpy.run_path(str(ROOT / script), run_name='__main__')
            except SystemExit as error:
                code = error.code
    return calls, code, stdout.getvalue(), stderr.getvalue()


def payload(call):
    assert call.headers['Authorization'] == 'rimuhosting apikey=offline-key'
    return json.loads(call.body)['new_order_request']


source = {'vps_order_oid_to_clone': 123456}
for selection in ([], ['--image_id', '789012']):
    calls, code, stdout, stderr = run(['--clone_order_oid', '123456', *selection,
                                     '--domain_name', 'copy.example.com', '--progress'])
    assert code == 0 and 'Offline result' in stdout and not stderr
    assert len(calls) == 1
    assert calls[0].method == 'POST' and calls[0].url == 'https://example.invalid/r/orders/new-vps'
    expected = dict(source, domain_name='copy.example.com')
    if selection:
        expected['optional_image_id'] = 789012
    assert payload(calls[0]) == {'instantiation_via_clone_options': expected}
    assert 'text/event-stream' in calls[0].headers['Accept']

# Selected images can belong to the target itself, or to a separate source VM.
for selection, expected in [
        (['--image_id', '789012'], {'vps_order_oid_to_clone': 654321, 'optional_image_id': 789012}),
        (['--clone_order_oid', '123456'], source),
        (['--clone_order_oid', '123456', '--image_id', '789012'], dict(source, optional_image_id=789012))]:
    calls, code, stdout, stderr = run(['--reinstall_order_oid', '654321', *selection])
    assert code == 0 and 'Offline result' in stdout and not stderr
    assert len(calls) == 2 and calls[0].method == 'GET'
    assert calls[1].method == 'PUT'
    assert calls[1].url == 'https://example.invalid/r/orders/order-654321-na.com/vps/reinstall'
    assert payload(calls[1]) == {'instantiation_via_clone_options': expected, 'dc_location': None}

# JSON clone configuration accepts CLI overrides and retains shared request fields.
config = {'instantiation_via_clone_options': dict(source, optional_image_id=10),
          'meta_data': {'purpose': 'offline'}, 'vps_parameters': {'memory_mb': 1024}}
calls, code, _, _ = run(['--extra_server_json', json.dumps(config), '--image_id', '789012',
                         '--domain_name', 'override.example.com', '--memory_mb', '2048',
                         '--disk_space_gb', '30', '--disk_space_2_gb', '0', '--dc_location', 'DCTEST'])
assert code == 0 and len(calls) == 1
assert payload(calls[0]) == {
    'instantiation_via_clone_options': dict(source, optional_image_id=789012, domain_name='override.example.com'),
    'meta_data': {'purpose': 'offline'}, 'dc_location': 'DCTEST',
    'vps_parameters': {'memory_mb': 2048, 'disk_space_mb': 30720, 'disk_space_2_mb': 0}}

with tempfile.TemporaryDirectory(prefix='mkvm-clone-config-') as directory:
    config_file = Path(directory) / 'clone.json'
    config_file.write_text(json.dumps({'instantiation_via_clone_options': source}))
    calls, code, _, _ = run(['--server_json_file', str(config_file), '--clone_order_oid', '654321'])
    assert code == 0 and len(calls) == 1
    assert payload(calls[0]) == {'instantiation_via_clone_options': {'vps_order_oid_to_clone': 654321}}

calls, code, _, _ = run(['--reinstall_order_oid', '654321', '--image_id', '789012', '--memory_mb', '2048'])
assert code == 0 and len(calls) == 2
assert payload(calls[1])['vps_parameters'] == {'memory_mb': 2048, 'disk_space_mb': None}

calls, code, _, _ = run(['--clone_order_oid', '123456', '--image_id', '789012'], script='pricing.py')
assert code == 0 and len(calls) == 1 and calls[0].method == 'PUT'
assert calls[0].url == 'https://example.invalid/r/pricing-plans/new-vm-pricing'
assert payload(calls[0]) == {'instantiation_via_clone_options':
                            dict(source, optional_image_id=789012, domain_name='notexample.com')}

# Existing distribution installs retain their request shape.
calls, code, _, _ = run(['--domain_name', 'fresh.example.com', '--distro', 'deb13.64'])
assert code == 0 and len(calls) == 1
assert payload(calls[0]) == {'instantiation_options': {'domain_name': 'fresh.example.com', 'distro': 'deb13.64'},
                            'vps_parameters': {}}

invalid = [
    ['--image_id', '789012'], ['--clone_order_oid', '0'], ['--image_id', '-1'],
    ['--clone_order_oid', '123456', '--distro', 'deb13.64'],
    ['--clone_order_oid', '123456', '--cloud_config', '/nonexistent/offline-config'],
    ['--clone_order_oid', '123456', '--extra_server_json', json.dumps({'instantiation_options': {'password': 'test'}})],
]
for clone in ({}, [], {'vps_order_oid_to_clone': 0}, {'vps_order_oid_to_clone': True},
              {'vps_order_oid_to_clone': '123456'}, dict(source, optional_image_id=0)):
    invalid.append(['--extra_server_json', json.dumps({'instantiation_via_clone_options': clone})])
for arguments in invalid:
    calls, code, stdout, stderr = run(arguments)
    assert code and not calls and not stdout and stderr, (arguments, code, stderr)

for arguments in (['--clone_order_oid', '123456'], ['--reinstall_order_oid', '654321', '--image_id', '789012']):
    calls, code, stdout, stderr = run([*arguments, '--is_disable_calls'])
    assert code == 1 and not calls and not stdout and 'disabled' in stderr.lower()

calls, code, stdout, stderr = run(['--clone_order_oid', '123456'], failure=True)
assert code == 1 and len(calls) == 1 and not stdout and stderr  # No creation retry.

# Library callers can use the same JSON contract without mutating their template.
with patch.object(rimuapi, 'load_settings', return_value=None):
    api = rimuapi.Api(key='offline-key')
before = deepcopy(config)
with patch.object(api, '_Api__send_request') as send:
    api.create(config)
    assert send.call_args.kwargs['data']['new_order_request'] == config
    api.reinstall(654321, config)
    assert send.call_args.kwargs['data']['new_order_request'] == config
assert config == before

print('VM clone request checks passed (no live API calls).')
