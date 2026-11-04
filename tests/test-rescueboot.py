"""Rescue options, library validation and safe output; all API operations are mocked."""
from offline import ROOT
import contextlib
import io
import json
import runpy
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import rimuapi
from outputformat import format_human


with patch.object(rimuapi, 'load_settings', return_value=None):
    api = rimuapi.Api(key='offline-rescue-key')

# Invalid inputs must fail before any mutating API request.
with patch.object(api, '_Api__send_request') as send:
    for keys in (None, [], ['  '], [' \n \r\n '], 'ssh-ed25519 AAAA agent', [None], [7]):
        try:
            api.rescue_boot(123456, ssh_public_keys=keys)
        except rimuapi.HumanReadableException:
            pass
        else:
            raise AssertionError(('Invalid rescue key input accepted', keys))
    send.assert_not_called()
    callback = Mock()
    api.rescue_boot(123456, [' ssh-ed25519 AAAA agent \n \r\nssh-ed25519 BBBB other\r\n'], on_progress=callback)
    assert send.call_args.kwargs['data'] == {'rescue_boot_request': {
        'rescue_ssh_public_keys': ['ssh-ed25519 AAAA agent', 'ssh-ed25519 BBBB other'],
        'is_add_users_ssh_keys': False,
        'rescue_ssh': True}}
    assert send.call_args.kwargs['on_progress'] is callback
    assert send.call_args.kwargs['json_root'] == 'post_rescue_boot_response'

script = ROOT / 'vmctl.py'
with tempfile.TemporaryDirectory() as directory:
    keys = Path(directory) / 'agent.pub'
    keys.write_text('ssh-ed25519 BBBB second\n\nssh-ed25519 CCCC third\n', encoding='utf-8')
    fake = Mock()
    with patch.object(rimuapi, 'load_settings', return_value=None), \
            patch.object(rimuapi, 'Api', return_value=fake), \
            patch.object(sys, 'argv', [str(script), 'rescueboot', '--order_oid', '123456',
                                      '--ssh_public_key', 'ssh-ed25519 AAAA first',
                                      '--ssh_public_key_file', str(keys), '--is_add_users_ssh_keys']), \
            contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(str(script), run_name='__main__')
    args = fake.rescue_boot.call_args
    assert args.args == (123456,)
    assert args.kwargs['ssh_public_keys'] == ['ssh-ed25519 AAAA first',
                                             'ssh-ed25519 BBBB second\n\nssh-ed25519 CCCC third\n']
    assert args.kwargs['is_add_users_ssh_keys'] is True

    for options in (['restart', '--ssh_public_key', 'ssh-ed25519 AAAA agent'],
                    ['start', '--is_add_users_ssh_keys'],
                    ['status', '--ssh_public_key_file', str(keys)],
                    ['rescueboot'], ['rescueboot', '--ssh_public_key', '  '],
                    ['rescueboot', '--ssh_public_key_file', str(keys) + '.missing']):
        with patch.object(rimuapi, 'load_settings', return_value=None), \
                patch.object(rimuapi, 'Api') as constructor, \
                patch.object(sys, 'argv', [str(script), '--order_oid', '123456'] + options), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            try:
                runpy.run_path(str(script), run_name='__main__')
            except SystemExit as error:
                assert error.code == 2
            else:
                raise AssertionError(('Invalid command accepted', options))
        constructor.assert_not_called()
        assert stdout.getvalue() == '' and 'error:' in stderr.getvalue()

response = {'post_rescue_boot_response': {
    'rescue_messages': ['Temporary keys installed'], 'ssh_host': '192.0.2.10', 'ssh_port': 22,
    'running_vps_info': {'is_rescue_boot': True},
    'request': {'rescue_password': 'SECRET_PASSWORD', 'rescue_ssh_public_keys': ['SECRET_KEY']}}}
text = format_human(response)
for expected in ('Temporary keys installed', 'host=192.0.2.10', 'port=22', 'rescue boot=True'):
    assert expected in text, (expected, text)
assert 'SECRET' not in text

# Short, minimal and full selection must preserve the agent's connection/status fields.
import requests
http = requests.Response()
http.status_code, http.reason = 200, 'OK'
http.headers['content-type'] = 'application/json'
http._content = json.dumps(response).encode()
with requests.Session() as session:
    session.trust_env = False
    with patch.object(session, 'send', return_value=http) as send, \
            patch.object(rimuapi, 'Session', return_value=session):
        for detail in ('short', 'minimal', 'full'):
            api.detail = detail
            data = json.loads(api.rescue_boot(123456, ['ssh-ed25519 AAAA agent']))
            if detail == 'short':
                data = data['result']
                assert data['running_vps_info']['is_rescue_boot'] is True
                assert data['ssh_host'] == '192.0.2.10' and data['ssh_port'] == 22
                assert 'request' not in data
            elif detail == 'minimal':
                assert data['ssh_host'] == '192.0.2.10' and data['running_vps_info']['is_rescue_boot'] is True
            else:
                assert data == response
        assert send.call_count == 3

# Keep all nonempty lines, including malformed keys, for the backend's complete validation.
# A validation failure must surface normally and must never replay the rescue request.
http = requests.Response()
http.status_code, http.reason = 400, 'Bad Request'
http.headers['content-type'] = 'application/json'
http._content = json.dumps({'post_rescue_boot_response': {
    'status_code': 400, 'response_type': 'ERROR',
    'error_info': {'human_readable_message': 'Invalid rescue SSH public key'}}}).encode()
with requests.Session() as session:
    session.trust_env = False
    with patch.object(session, 'send', return_value=http) as send, \
            patch.object(rimuapi, 'Session', return_value=session):
        for supplied in (['malformed'], ['ssh-ed25519 AAAA agent\n malformed \n']):
            send.reset_mock()
            try:
                api.rescue_boot(123456, supplied)
            except rimuapi.HumanReadableException as error:
                assert str(error) == 'HTTP 400 Bad Request: Invalid rescue SSH public key'
            else:
                raise AssertionError('Backend key validation failure was ignored')
            assert send.call_count == 1
            body = json.loads(send.call_args.args[0].body)['rescue_boot_request']
            assert body['rescue_ssh_public_keys'][-1] == 'malformed'

print('Rescue boot regression checks passed (no live API calls).')
