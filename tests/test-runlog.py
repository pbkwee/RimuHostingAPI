"""Exercise optional run logs and human transport output without contacting any service."""
from offline import ROOT
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import stat
import sys
from http.client import responses
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
import rimuapi
import runlog
from outputformat import strip_color


body = {'post_backup_response': {
    'status_code': 200, 'status_message': 'OK', 'response_type': 'OK',
    'human_readable_message': 'Backup completed.', 'backup_messages': ['Copied root disk'],
    'backup_image': {'optional_image_id': 12, 'file_name': 'root.img', 'size_mb': 512},
    'removed_disk_images': [], 'running_vps_info': {'disk_images': []}}}


def response(value, code=200, content_type='application/json'):
    result = requests.Response()
    result.status_code, result.reason = code, responses[code]
    result.headers.update({'Content-Type': content_type, 'Set-Cookie': 'private-cookie'})
    result._content = (json.dumps(value) if content_type == 'application/json' else value).encode()
    return result


def client():
    return rimuapi.Api(key='offline-log-key')


session = Mock()
session.prepare_request.side_effect = lambda request: request.prepare()
with tempfile.TemporaryDirectory(prefix='rimuapi-runlogs-') as directory, \
        patch.object(rimuapi, 'Session', return_value=session), \
        patch.object(rimuapi, 'load_settings', return_value=None), \
        patch.dict(os.environ, {'RIMUHOSTING_LOGDIR': directory, 'RIMUHOSTING_BASEURL': 'https://example.invalid', 'RIMUHOSTING_APIKEY': 'offline-log-key'}):
    root = Path(directory)
    for output in ('json', 'flat', 'raw', 'human'):
        session.send.return_value = response(body)
        session.send.reset_mock()
        before = set(root.iterdir())
        with patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456', '--output', output]), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        created = set(root.iterdir()) - before
        assert len(created) == 1
        run = created.pop()
        assert run.name.startswith('mksnapshot-') and 'Z-' in run.name
        assert (run / 'stdout.txt').read_text() == stdout.getvalue()
        assert (run / 'stderr.txt').read_text() == stderr.getvalue() == ''
        assert json.loads((run / '001-response.json').read_text()) == body
        assert 'Backup completed.' in (run / 'summary.txt').read_text()
        http = (run / '001-http.txt').read_text()
        assert 'HTTP 200 OK' in http and json.dumps(body) in http
        assert 'private-cookie' not in http and 'offline-log-key' not in http
        meta = json.loads((run / 'meta.json').read_text())
        assert meta['exit_code'] == 0 and len(meta['requests']) == 1
        assert meta['requests'][0]['http_status'] == meta['requests'][0]['status_code'] == 200
        assert stat.S_IMODE(run.stat().st_mode) == 0o700
        assert all(stat.S_IMODE(file.stat().st_mode) == 0o600 for file in run.iterdir())
        session.send.assert_called_once()
        if output == 'human':
            assert stdout.getvalue().startswith('Results\n') and 'Created backup' in stdout.getvalue()
        elif output in ('json', 'raw'):
            assert isinstance(json.loads(stdout.getvalue()), dict)

    # Styling is human-only; even forced terminal colors never enter console logs.
    for output in ('human', 'json', 'flat', 'raw'):
        before = set(root.iterdir())
        session.send.return_value = response(body)
        session.send.reset_mock()
        with patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456',
                                       '--output', output, '--color', 'always']), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        run = (set(root.iterdir()) - before).pop()
        assert ('\x1b' in stdout.getvalue()) == (output == 'human')
        assert (run / 'stdout.txt').read_text() == strip_color(stdout.getvalue())
        assert '\x1b' not in (run / 'summary.txt').read_text()
        assert json.loads((run / '001-response.json').read_text()) == body
        session.send.assert_called_once()

    # Error summaries use stderr's styling policy and their saved text remains plain.
    before = set(root.iterdir())
    session.send.return_value = response({'post_backup_response': {
        'status_code': 406, 'response_type': 'ERROR',
        'error_info': {'field_name': 'order_oid', 'human_readable_message': 'VM is stopped'}}}, 406)
    with patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456',
                                   '--output', 'human', '--color', 'always']), \
            contextlib.redirect_stdout(io.StringIO()) as stdout, \
            contextlib.redirect_stderr(io.StringIO()) as stderr:
        try:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError('Validation failure must exit nonzero')
    run = (set(root.iterdir()) - before).pop()
    assert stdout.getvalue() == '' and '\x1b[1;31mError' in stderr.getvalue()
    assert (run / 'stderr.txt').read_text() == strip_color(stderr.getvalue())
    assert '\x1b' not in (run / 'summary.txt').read_text()

    # One command can make multiple API calls (e.g. lookup followed by mutation).
    before = set(root.iterdir())
    session.send.return_value = response(body)
    with patch.object(sys, 'argv', ['mksnapshot.py']), rimuapi.command():
        api = client()
        api.create_snapshot(123456)
        api.create_snapshot(123456)
    run = (set(root.iterdir()) - before).pop()
    assert json.loads((run / '002-response.json').read_text()) == body
    assert len(json.loads((run / 'meta.json').read_text())['requests']) == 2

    # A non-JSON HTTP failure preserves its response; no fake JSON is invented.
    before = set(root.iterdir())
    session.send.return_value = response('<html>Offline failure</html>', 503, 'text/html')
    with patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456']), \
            contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
        try:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError('HTTP failure must exit nonzero')
    run = (set(root.iterdir()) - before).pop()
    assert (run / '001-response.json').read_bytes() == b''
    assert '<html>Offline failure</html>' in (run / '001-http.txt').read_text()
    assert stdout.getvalue() == '' and 'Traceback' not in stderr.getvalue()
    assert json.loads((run / 'meta.json').read_text())['exit_code'] == 1

    # Preserve consumed SSE bytes without buffering progress or reading beyond its final result.
    class Wire:
        def __init__(self, text):
            self.data = text.encode('utf-8')
            self.consumed = 0
            self.closed = False

        def stream(self, amount, decode_content=True):
            assert amount == 1
            for byte in self.data:
                self.consumed += 1
                yield bytes([byte])

        def close(self):
            self.closed = True

        def release_conn(self):
            pass

    for code in (200, 406):
        final = json.loads(json.dumps(body))
        final['post_backup_response'].update(status_code=code, status_message=responses[code],
                                              response_type='OK' if code == 200 else 'ERROR')
        if code == 406:
            final['post_backup_response']['error_info'] = {'human_readable_message': 'VM is canceled.'}
        prefix = '\ufeffevent: progress\r\ndata: {"message":"Copying café"}\r\n\r\n'
        terminal = 'event: result\r\ndata: ' + json.dumps(final) + '\r\n\r\n'
        wire = Wire(prefix + terminal + 'event: progress\ndata: {"message":"Do not read"}\n\n')
        streamed = requests.Response()
        streamed.status_code, streamed.reason = 200, 'OK'
        streamed.headers['Content-Type'] = 'text/event-stream; charset=UTF-8'
        streamed.raw = wire
        session.send.return_value = streamed
        before = set(root.iterdir())
        messages = []

        def progress(message):
            messages.append(message)
            current = (set(root.iterdir()) - before).pop()
            captured = (current / '001-http.txt').read_bytes()
            assert 'Copying café'.encode() in captured and b'event: result' not in captured

        api = client()
        try:
            result = api.create_snapshot(123456, on_progress=progress)
            assert code == 200 and 'Backup completed.' in result
        except rimuapi.HumanReadableException as error:
            assert code == 406 and 'HTTP 406 Not Acceptable: VM is canceled.' == str(error)
        run = (set(root.iterdir()) - before).pop()
        assert messages == ['Copying café'] and wire.closed
        assert json.loads((run / '001-response.json').read_text()) == final
        captured = (run / '001-http.txt').read_bytes()
        assert b'\xef\xbb\xbf' in captured and b'Do not read' not in captured
        assert wire.consumed < len(wire.data)
        request = json.loads((run / 'meta.json').read_text())['requests'][0]
        assert request['http_status'] == 200 and request['status_code'] == code

    # A connection failure leaves empty request response files and still records its failure.
    before = set(root.iterdir())
    session.send.side_effect = requests.exceptions.ConnectionError('offline connection failure')
    try:
        client().create_snapshot(123456)
    except requests.exceptions.ConnectionError:
        pass
    else:
        raise AssertionError('Connection failures must propagate to library callers')
    run = (set(root.iterdir()) - before).pop()
    assert (run / '001-http.txt').read_bytes() == (run / '001-response.json').read_bytes() == b''
    assert 'offline connection failure' in json.loads((run / 'meta.json').read_text())['error']
    session.send.side_effect = None

    before = set(root.iterdir())
    refused = {'post_backup_response': {'status_code': 406, 'response_type': 'ERROR',
        'error_info': {'human_readable_message': 'VM is canceled.', 'field_name': 'order_oid'},
        'removed_disk_images': []}}
    session.send.return_value = response(refused, 406)
    with patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456', '--output', 'human']), \
            contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
        try:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError('Human validation output must preserve failure exit status')
    run = (set(root.iterdir()) - before).pop()
    assert stdout.getvalue() == '' and 'Traceback' not in stderr.getvalue()
    assert 'Results' in stderr.getvalue() and 'field=order_oid' in stderr.getvalue()
    assert json.loads((run / '001-response.json').read_text()) == refused

    before = set(root.iterdir())
    session.send.reset_mock()
    with patch.object(sys, 'argv', ['mksnapshot.py', '--help']), contextlib.redirect_stdout(io.StringIO()):
        try:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 0
    run = (set(root.iterdir()) - before).pop()
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['exit_code'] == 0 and 'error' not in meta and meta['requests'] == []
    session.send.assert_not_called()

    # A successful mutation must remain successful even with an escaped lone surrogate in its JSON.
    before = set(root.iterdir())
    unusual = json.loads(json.dumps(body))
    unusual['post_backup_response']['backup_image']['label'] = '\ud800'
    session.send.return_value = response(unusual)
    result = client().create_snapshot(123456)
    assert json.loads(result)['result']['backup_image']['label'] == '\ud800'
    run = (set(root.iterdir()) - before).pop()
    assert json.loads((run / '001-response.json').read_text()) == unusual

    # Explicit CLI debug wins over IS_DEBUG=False, but URL credentials never enter its logs.
    before = set(root.iterdir())
    session.send.return_value = response(refused, 406)
    with patch.object(rimuapi, 'load_settings', return_value=SimpleNamespace(IS_DEBUG=False, RIMUHOSTING_BASEURL='https://settings-user:settings-password@settings.invalid')), \
            patch.dict(os.environ, {'RIMUHOSTING_BASEURL': 'https://fixture-user:fixture-password@example.invalid'}), \
            patch.object(rimuapi, 'isDebug', False), \
            patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456', '--debug']), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
        try:
            runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError('Debug failure must remain nonzero')
    run = (set(root.iterdir()) - before).pop()
    assert 'Traceback' in stderr.getvalue()
    assert all(b'fixture-password' not in file.read_bytes() and b'settings-password' not in file.read_bytes()
               for file in run.iterdir())

    # Directory failure prevents the HTTP mutation. A later disk write failure does not hide success.
    blocked = root / 'not-a-directory'
    blocked.write_text('fixture')
    api = client()
    api.log_dir = str(blocked)
    session.send.reset_mock()
    try:
        api.create_snapshot(123456)
    except rimuapi.HumanReadableException as error:
        assert 'no API request was sent' in str(error)
    else:
        raise AssertionError('Unusable log destination must fail before sending')
    session.send.assert_not_called()

    session.send.return_value = response(body)
    api.log_dir = directory
    original_write = runlog.RunLog.write

    def disk_full(log, name, text):
        if name.endswith('-response.json'):
            log.warn(OSError('offline disk full'))
        else:
            original_write(log, name, text)

    with patch.object(runlog.RunLog, 'write', disk_full), contextlib.redirect_stderr(io.StringIO()) as stderr:
        assert 'Backup completed.' in api.create_snapshot(123456)
    assert 'Warning:' in stderr.getvalue()

    # Environment overrides the Python settings file; an explicit empty value disables logging.
    settings = SimpleNamespace(RIMUHOSTING_LOGDIR=str(root / 'settings-dir'))
    with patch.object(rimuapi, 'load_settings', return_value=settings):
        assert client().log_dir == directory
        with patch.dict(os.environ, {'RIMUHOSTING_LOGDIR': ''}):
            assert client().log_dir is None
        with patch.dict(os.environ):
            os.environ.pop('RIMUHOSTING_LOGDIR')
            assert client().log_dir == settings.RIMUHOSTING_LOGDIR
            session.send.return_value = response(body)
            with patch.object(rimuapi, 'load_settings', return_value=settings) as load, \
                    patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456']), \
                    contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(ROOT / 'mksnapshot.py'), run_name='__main__')
            load.assert_called_once_with('.rimuhosting')
            assert len(list(Path(settings.RIMUHOSTING_LOGDIR).iterdir())) == 1

print('Run logging and human transport checks passed (no live API calls).')
