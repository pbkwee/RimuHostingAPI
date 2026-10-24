"""Run with python3 tests/test-progress.py; all HTTP operations use offline wire fixtures."""
from offline import ROOT
import contextlib
from copy import deepcopy
import io
import json
import os
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
import requests
import rimuapi

root = ROOT
with patch.object(rimuapi, 'load_settings', return_value=None), \
        patch.dict(os.environ, {'RIMUHOSTING_BASEURL': 'https://example.invalid'}):
    api = rimuapi.Api(key='offline-progress-key')

snapshot = {'post_backup_response': {
    'status_code': 200, 'status_message': 'OK', 'response_type': 'OK',
    'backup_image': {'optional_image_id': 12, 'label': 'Before upgrade'},
    'removed_disk_images': [], 'backup_messages': ['Backup completed'],
    'running_vps_info': {'disk_images': []}, 'human_readable_message': 'VM backup completed.'}}


def options(detail='short', output='json', jsonpath=None):
    return SimpleNamespace(detail=detail, output=output, jsonpath=jsonpath,
                           is_pretty=False, is_disable_calls=False)


def event(name, body, newline='\n'):
    return 'event: ' + name + newline + 'data: ' + json.dumps(body, ensure_ascii=False) + newline * 2


class Wire:
    def __init__(self, text, failure=None):
        self.data, self.consumed, self.closed = text.encode('utf-8'), 0, False
        self.failure = failure

    def stream(self, amount, decode_content=True):
        assert amount == 1, 'Progress must not wait for a full response buffer'
        for byte in self.data:
            self.consumed += 1
            yield bytes([byte])
        if self.failure is not None:
            raise self.failure

    def close(self):
        self.closed = True

    def release_conn(self):
        pass


def stream(text, failure=None):
    response = requests.Response()
    response.status_code, response.reason = 200, 'OK'
    response.headers['content-type'] = 'text/event-stream; charset=UTF-8'
    response.raw = Wire(text, failure)
    response.close = Mock(wraps=response.close)
    return response


def json_response(body, code=200, reason='OK'):
    response = requests.Response()
    response.status_code, response.reason = code, reason
    response.headers['content-type'] = 'application/json'
    response._content = json.dumps(body).encode()
    response.close = Mock(wraps=response.close)
    return response


session = Mock()
session.prepare_request.side_effect = lambda request: request.prepare()


def use(response):
    session.send.reset_mock()
    session.send.side_effect = None
    session.send.return_value = response


def assert_request(progress=True):
    assert session.send.call_count == 1, 'A backup POST must not be retried'
    request = session.send.call_args.args[0]
    assert request.method == 'POST'
    assert request.url == 'https://example.invalid/r/orders/order-123456-na.com/vps/backups'
    assert request.headers['Authorization'] == 'rimuhosting apikey=offline-progress-key'
    assert request.headers['Accept'] == ('text/event-stream, application/json;q=0.9' if progress else 'application/json')
    assert json.loads(request.body) == {'post_backup_request': {'backup_name': 'Before upgrade'}}
    assert session.send.call_args.kwargs == dict(timeout=(30, 3600), verify=True, **({'stream': True} if progress else {}))


def call(callback=None, output=None):
    return api.create_snapshot(123456, label='Before upgrade', output=output, on_progress=callback)


with patch.object(rimuapi, 'Session', return_value=session):
    # Real Requests decoding receives UTF-8 characters and CRLF boundaries one byte at a time.
    for newline in ('\n', '\r\n', '\r'):
        prefix = '\ufeff: heartbeat' + newline * 2 + 'id: 123' + newline + 'retry: 1' + newline * 2
        prefix += event('status', {'status_code': 202, 'human_readable_message': 'Accepted'}, newline)
        prefix += 'event: progress' + newline + 'data: {"message":' + newline + 'data: "Copying café"}' + newline * 2
        prefix += event('future-event', {'ignored': True}, newline)
        suffix = event('result', snapshot, newline)
        response = stream(prefix + suffix + event('progress', {'message': 'Must not read'}, newline))
        use(response)
        messages = []

        def progress(message):
            assert response.raw.consumed <= len(prefix.encode('utf-8')), 'Progress was buffered until the result'
            messages.append(message)

        result = json.loads(call(progress))
        assert result == {'result': {key: value for key, value in snapshot['post_backup_response'].items()
                                     if key not in ('status_code', 'status_message', 'response_type')}}
        assert messages == ['Accepted', 'Copying café']
        assert response.raw.consumed == len((prefix + suffix).encode('utf-8')) - (newline == '\r\n')
        assert response.raw.closed
        response.close.assert_called_once_with()
        assert_request()

    # Every existing output selector receives the final envelope, including raw output.
    for output in (options(), options('full'), options(output='flat'), options(output='raw'),
                   options('minimal'), options('minimal', jsonpath='$.backup_image.optional_image_id')):
        use(json_response(snapshot))
        expected = call(output=output)
        response = stream(event('result', snapshot))
        use(response)
        actual = call(lambda message: None, output)
        assert actual == expected
        response.close.assert_called_once_with()
        assert_request()

    # An older server can ignore the SSE Accept header and return ordinary JSON.
    for output in (options(), options('full'), options(output='raw')):
        response = json_response(snapshot)
        use(response)
        expected = call(output=output)
        assert_request(False)
        response.close.assert_not_called()
        response = json_response(snapshot)
        use(response)
        messages = []
        assert call(messages.append, output) == expected
        assert messages == []
        response.close.assert_called_once_with()
        assert_request()

    for code, reason, message in ((429, 'Too Many Requests', 'Please wait one hour'),
                                   (500, 'Internal Server Error', 'Backup result could not be verified')):
        failed = deepcopy(snapshot)
        failed['post_backup_response'].update(status_code=code, status_message=reason, response_type='ERROR',
                                             error_info={'human_readable_message': message})
        for response in (stream(event('result', failed)), json_response(failed, code, reason)):
            use(response)
            try:
                call(lambda message: None)
            except rimuapi.HumanReadableException as error:
                assert str(error) == 'HTTP %s %s: %s' % (code, reason, message)
            else:
                raise AssertionError('Terminal backup failure was hidden')
            response.close.assert_called_once_with()
            assert_request()

    invalid_results = [None, [], {}, {'post_backup_response': None}, {'post_backup_response': {}},
                       {'post_backup_response': {'status_code': True, 'response_type': 'OK'}},
                       {'post_backup_response': {'status_code': '200', 'response_type': 'OK'}},
                       {'post_backup_response': {'status_code': 199, 'response_type': 'OK'}},
                       {'post_backup_response': {'status_code': 200}},
                       {'post_backup_response': {'status_code': 200, 'response_type': 'ERROR'}},
                       {'post_backup_response': {'status_code': 500, 'response_type': 'OK'}}]
    invalid_streams = [event('result', body) for body in invalid_results] + [
        '', ': heartbeat\n\n', event('progress', {'message': 'Copying'}),
        event('result', snapshot).rstrip('\n'), 'event: result\ndata: {bad JSON}\n\n',
        event('progress', []), event('progress', {'message': 123})]
    for text in invalid_streams:
        response = stream(text)
        use(response)
        try:
            call(lambda message: None)
        except rimuapi.HumanReadableException as error:
            assert 'outcome is unknown' in str(error)
            assert 'before repeating the request' in str(error)
            if '{bad JSON}' in text:
                assert isinstance(error.__cause__, ValueError)
        else:
            raise AssertionError('Invalid or unfinished stream was treated as success: ' + text)
        response.close.assert_called_once_with()
        assert_request()

    failure = requests.exceptions.ChunkedEncodingError('offline dropped connection')
    response = stream(event('progress', {'message': 'Copying'}), failure)
    use(response)
    try:
        call(lambda message: None)
    except rimuapi.HumanReadableException as error:
        assert 'outcome is unknown' in str(error)
        assert error.__cause__ is failure
    else:
        raise AssertionError('Disconnected stream was treated as success')
    response.close.assert_called_once_with()
    assert_request()

    session.send.reset_mock()
    session.send.side_effect = failure
    try:
        call(lambda message: None)
    except rimuapi.HumanReadableException as error:
        assert error.__cause__ is failure
        assert 'outcome is unknown' in str(error)
    else:
        raise AssertionError('Request connection failure was hidden')
    assert_request()

    response = stream(event('progress', {'message': 'Copying'}))
    use(response)
    callback_error = RuntimeError('offline callback failure')
    try:
        call(Mock(side_effect=callback_error))
    except RuntimeError as error:
        assert error is callback_error
    else:
        raise AssertionError('Callback failure was hidden')
    response.close.assert_called_once_with()

    # Progress writes to stderr immediately; final selected JSON remains the only stdout output.
    class FlushedOutput(io.StringIO):
        flushes = 0

        def flush(self):
            self.flushes += 1
            super().flush()

    response = stream(event('progress', {'message': 'Copying'}) + event('result', snapshot))
    use(response)
    with patch.object(rimuapi, 'load_settings', return_value=None), \
            patch.object(rimuapi, 'Api', return_value=api), \
            patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456', '--label', 'Before upgrade', '--progress']), \
            contextlib.redirect_stdout(io.StringIO()) as stdout, \
            contextlib.redirect_stderr(FlushedOutput()) as stderr:
        runpy.run_path(str(root / 'mksnapshot.py'), run_name='__main__')
    assert stderr.getvalue() == 'Copying\n'
    assert stderr.flushes > 0
    assert json.loads(stdout.getvalue())['result']['backup_image']['optional_image_id'] == 12
    assert_request()

    response = stream('')
    use(response)
    with patch.object(rimuapi, 'load_settings', return_value=None), \
            patch.object(rimuapi, 'Api', return_value=api), \
            patch.object(sys, 'argv', ['mksnapshot.py', '--order_oid', '123456', '--progress']), \
            contextlib.redirect_stdout(io.StringIO()) as stdout, \
            contextlib.redirect_stderr(io.StringIO()) as stderr:
        try:
            runpy.run_path(str(root / 'mksnapshot.py'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 1
            assert stderr.getvalue().startswith('Error: ')
            assert 'Traceback' not in stderr.getvalue()
        else:
            raise AssertionError('CLI must fail if the backup outcome is unknown')
    assert stdout.getvalue() == ''

    # Shared options work for endpoints with progress and those returning ordinary JSON.
    catalog = {'get_orders_response': {
        'status_code': 200, 'response_type': 'OK', 'human_readable_message': 'Orders loaded',
        'about_orders': [{'order_oid': 123456}]}}
    use(json_response(catalog))
    expected = api.orders()
    api.progress = True
    try:
        for response in (json_response(catalog), stream(event('progress', {'message': 'Loading orders'}) + event('result', catalog))):
            use(response)
            with contextlib.redirect_stderr(FlushedOutput()) as stderr:
                assert api.orders() == expected
            assert stderr.getvalue() == ('Loading orders\n' if isinstance(response.raw, Wire) else '')
            assert session.send.call_args.args[0].headers['Accept'] == 'text/event-stream, application/json;q=0.9'
            assert session.send.call_args.kwargs['stream'] is True
            assert session.send.call_count == 1
            response.close.assert_called_once_with()
    finally:
        api.progress = False

    messages = []
    api.on_progress = messages.append
    try:
        use(stream(event('progress', {'message': 'Loading orders'}) + event('result', catalog)))
        assert api.orders() == expected
        assert messages == ['Loading orders']
    finally:
        api.on_progress = None

    # A final 202 preserves the ordinary result for an endpoint accepting asynchronous work.
    accepted = {'post_new_vps_response': {
        'status_code': 202, 'response_type': 'OK', 'human_readable_message': 'Creation accepted'}}
    arguments = {'instantiation_options': {'domain_name': 'example.invalid'}}
    use(json_response(accepted, 202, 'Accepted'))
    expected = api.create(arguments)
    api.progress = True
    try:
        use(stream(event('status', {'status_code': 202, 'human_readable_message': 'Accepted'}) + event('result', accepted)))
        with contextlib.redirect_stderr(io.StringIO()):
            assert api.create(arguments) == expected
        failed = deepcopy(catalog)
        failed['get_orders_response'].update(status_code=403, response_type='ERROR',
            error_info={'human_readable_message': 'Access refused'})
        use(stream(event('result', failed)))
        try:
            api.orders()
        except rimuapi.HumanReadableException as error:
            assert str(error) == 'HTTP 403 Forbidden: Access refused'
        else:
            raise AssertionError('Non-backup final failure was hidden')
        use(stream(event('result', snapshot)))
        try:
            api.orders()
        except rimuapi.HumanReadableException as error:
            assert 'outcome is unknown' in str(error)
        else:
            raise AssertionError('Wrong result envelope was accepted for another endpoint')
    finally:
        api.progress = False

# Every command forwards the shared flag without its own progress wiring.
commands = [
    ('lsvms.py', []), ('lsdistros.py', []), ('lsdcs.py', []),
    ('lsdiskimages.py', ['--order_oid', '123456']),
    ('mksnapshot.py', ['--order_oid', '123456']),
    ('vmctl.py', ['status', '--order_oid', '123456']),
    ('mkvm.py', ['--domain_name', 'example.invalid']),
    ('pricing.py', ['--domain_name', 'example.invalid']),
    ('chattrvm.py', ['--order_oid', '123456', '--memory_mb', '512']),
    ('rmvm.py', ['--order_oid', '123456']),
    ('rdns.py', ['--order_oid', '123456', '--ip', '192.0.2.1', '--domain_name', 'example.invalid']),
]
for script, arguments in commands:
    client = Mock()
    with patch.object(rimuapi, 'load_settings', return_value=None), \
            patch.object(rimuapi, 'Api', return_value=client), \
            patch.object(sys, 'argv', [script, '--progress', *arguments]), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        runpy.run_path(str(root / script), run_name='__main__')
    assert any(call.kwargs.get('output') is not None and call.kwargs['output'].progress
               for call in client.mock_calls), script

print('General progress checks passed (no live API calls).')
