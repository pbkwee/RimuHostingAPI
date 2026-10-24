"""Exercise settings discovery, credential precedence and TLS options with isolated files."""
from offline import ROOT
import argparse
import contextlib
import io
import json
import os
import runpy
import shutil
import sys
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import requests
import rimuapi


with tempfile.TemporaryDirectory(prefix='rimuapi-settings-') as directory:
    scratch = Path(directory)
    home = scratch / 'home'
    first = scratch / 'first-bin'
    second = scratch / 'second-bin'
    project = scratch / 'project'
    for folder in (home, first, second, project):
        folder.mkdir()
    home_settings = home / '.rimuhosting'
    first_settings = first / '.rimuhosting'
    second_settings = second / '.rimuhosting'
    home_settings.write_text(
        "ORIGIN = 'home'\nRIMUHOSTING_APIKEY = 'offline-settings-key'\n"
        "RIMUHOSTING_BASEURL = 'https://settings.invalid'\nRIMUHOSTING_ISVERIFYSSL = False\n")
    first_settings.write_text("raise AssertionError('PATH settings must not override home settings')\n")
    second_settings.write_text("raise AssertionError('Later PATH settings must not execute')\n")
    search_path = str(first) + os.pathsep + str(second)

    with patch.object(rimuapi.os, 'getcwd', return_value=str(project)), \
            patch.object(rimuapi.os.path, 'expanduser', return_value=str(home)), \
            patch.dict(os.environ, {'PATH': search_path, 'RIMUHOSTING_APIKEY': '', 'RIMUHOSTING_BASEURL': ''}):
        local_settings = project / '.rimuhosting'
        local_settings.write_text("ORIGIN = 'project'\n")
        assert rimuapi.load_settings('.rimuhosting').ORIGIN == 'project'
        local_settings.unlink()
        assert rimuapi.load_settings('.rimuhosting').ORIGIN == 'home'

        response = requests.Response()
        response.status_code = 200
        response.headers['content-type'] = 'application/json'
        response._content = json.dumps({'get_orders_response': {'about_orders': []}}).encode()
        session = Mock()
        session.prepare_request.side_effect = lambda request: request.prepare()
        session.send.return_value = response
        with patch.object(rimuapi, 'Session', return_value=session):
            for explicit, environment, expected in (
                ('offline-explicit-key', 'offline-env-key', 'offline-explicit-key'),
                (None, 'offline-env-key', 'offline-env-key'),
                (None, '', 'offline-settings-key'),
            ):
                session.send.reset_mock()
                with patch.dict(os.environ, {'RIMUHOSTING_APIKEY': environment}):
                    api = rimuapi.Api(key=explicit)
                    assert json.loads(api.orders()) == {'result': {'about_orders': []}}
                session.send.assert_called_once()
                request = session.send.call_args.args[0]
                assert request.url.startswith('https://settings.invalid/r/orders;')
                assert request.headers['Authorization'] == 'rimuhosting apikey=' + expected
                assert session.send.call_args.kwargs['verify'] is False

            with patch.dict(os.environ, {'RIMUHOSTING_BASEURL': 'https://environment.invalid'}):
                api = rimuapi.Api(key='offline-explicit-key')
                api.orders()
                assert session.send.call_args.args[0].url.startswith('https://environment.invalid/r/orders;')

        home_settings.unlink()
        first_settings.write_text("ORIGIN = 'first'\n")
        assert rimuapi.load_settings('.rimuhosting').ORIGIN == 'first'
        first_settings.unlink()
        second_settings.write_text("ORIGIN = 'second'\n")
        assert rimuapi.load_settings('.rimuhosting').ORIGIN == 'second'
        second_settings.unlink()
        assert rimuapi.load_settings('.rimuhosting') is None

        with patch.object(rimuapi, 'Session') as sessions:
            api = rimuapi.Api()
            assert api._is_ssl_verify is True
            try:
                api.orders()
            except Exception as error:
                assert 'API Key is required' in str(error)
            else:
                raise AssertionError('Authenticated calls must fail before transport without an API key')
            sessions.assert_not_called()

# Copy-and-edit setup works from the project folder without adding it to PATH.
with tempfile.TemporaryDirectory(prefix='rimuapi-template-') as directory:
    project = Path(directory) / 'project'
    home = Path(directory) / 'home'
    project.mkdir()
    home.mkdir()
    shutil.copyfile(ROOT / '.rimuhosting.example', project / '.rimuhosting')
    previous_directory = os.getcwd()
    os.chdir(project)
    try:
        session = Mock()
        session.prepare_request.side_effect = lambda request: request.prepare()
        body = {'get_orders_response': {'about_orders': [{'order_oid': 42, 'domain_name': 'vm.example'}]}}
        with patch.object(rimuapi.os.path, 'expanduser', return_value=str(home)), \
                patch.object(rimuapi, 'Session', return_value=session), \
                patch.dict(os.environ, {'RIMUHOSTING_OUTPUT': '', 'RIMUHOSTING_APIKEY': 'offline-template-key',
                                       'RIMUHOSTING_BASEURL': 'https://example.invalid'}):
            os.environ.pop('RIMUHOSTING_LOGDIR', None)
            api = rimuapi.Api()
            assert (api.output, api.progress, api.color, api.detail, api.is_pretty, api.wrap) == (
                'human', True, 'auto', 'short', True, False)
            for environment, arguments, expected in (
                ('', [], 'human'),
                ('json', [], 'json'),
                ('human', ['--output', 'json'], 'json'),
                ('json', ['--output', 'human'], 'human'),
                ('invalid', ['--output', 'json'], 'json'),
                ('', ['--output', 'raw'], 'raw'),
                ('', ['--output', 'flat'], 'flat'),
            ):
                response = requests.Response()
                response.status_code, response.reason = 200, 'OK'
                response.headers['content-type'] = 'application/json'
                response._content = json.dumps(body).encode()
                session.send.return_value = response
                session.send.reset_mock()
                with patch.dict(os.environ, {'RIMUHOSTING_OUTPUT': environment}), \
                        patch.object(sys, 'argv', ['lsvms.py', *arguments]), \
                        contextlib.redirect_stdout(io.StringIO()) as stdout, \
                        contextlib.redirect_stderr(io.StringIO()) as stderr:
                    runpy.run_path(str(ROOT / 'lsvms.py'), run_name='__main__')
                session.send.assert_called_once()
                assert session.send.call_args.args[0].headers['Accept'].startswith('text/event-stream')
                text = stdout.getvalue()
                assert stderr.getvalue() == ''
                if expected == 'human':
                    assert text.startswith('Results\n') and 'vm.example' in text
                elif expected in ('json', 'raw'):
                    assert isinstance(json.loads(text), dict)
                else:
                    assert 'domain_name=vm.example' in text
            # A quiet machine-readable run can override the human-friendly template.
            session.send.reset_mock()
            with patch.object(sys, 'argv', ['lsvms.py', '--output', 'json', '--no-progress', '--is_ugly']), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout:
                runpy.run_path(str(ROOT / 'lsvms.py'), run_name='__main__')
            session.send.assert_called_once()
            assert session.send.call_args.args[0].headers['Accept'] == 'application/json'
            assert '\n' not in stdout.getvalue().strip()
            assert json.loads(stdout.getvalue())['result']['about_orders'][0]['order_oid'] == 42
            assert len(list((project / 'runlogs').iterdir())) == 8

            # Each display preference reaches library calls and can be overridden by CLI options.
            settings_path = project / '.rimuhosting'
            template = settings_path.read_text()
            settings_path.write_text("RIMUHOSTING_OUTPUT = 'json'\nRIMUHOSTING_COLOR = 'never'\n"
                "RIMUHOSTING_DETAIL = 'full'\nRIMUHOSTING_PRETTY = False\nRIMUHOSTING_PROGRESS = False\nRIMUHOSTING_WRAP = True\n")
            api = rimuapi.Api()
            assert (api.output, api.progress, api.color, api.detail, api.is_pretty, api.wrap) == (
                'json', False, 'never', 'full', False, True)
            parser = argparse.ArgumentParser()
            rimuapi._addOutputArgument(parser)
            options = parser.parse_args([])
            assert (options.output, options.progress, options.color, options.detail, options.is_pretty, options.wrap) == (
                'json', False, 'never', 'full', False, True)
            options = parser.parse_args(['--output', 'human', '--progress', '--color', 'always',
                                         '--detail', 'minimal', '--is_pretty', '--no-wrap'])
            assert (options.output, options.progress, options.color, options.detail, options.is_pretty, options.wrap) == (
                'human', True, 'always', 'minimal', True, False)
            settings_path.write_text(template)

            # Wrapping is opt-in and does not discard any result text.
            long_message = 'The requested operation completed successfully ' * 8 + 'END'
            response._content = json.dumps({'get_orders_response': dict(body['get_orders_response'],
                human_readable_message=long_message)}).encode()
            for arguments, should_wrap in (([], False), (['--wrap'], True), (['--no-wrap'], False)):
                session.send.reset_mock()
                with patch.object(sys, 'argv', ['lsvms.py', '--output', 'human', '--color', 'never', *arguments]), \
                        contextlib.redirect_stdout(io.StringIO()) as stdout:
                    runpy.run_path(str(ROOT / 'lsvms.py'), run_name='__main__')
                session.send.assert_called_once()
                text = stdout.getvalue()
                assert (long_message in text) == (not should_wrap)
                assert 'END' in text
                if should_wrap:
                    assert all(len(line) <= 100 for line in text.splitlines())

            # Invalid defaults fail before any network call, and library callers may override them.
            with patch.dict(os.environ, {'RIMUHOSTING_OUTPUT': 'invalid'}):
                api = rimuapi.Api()
                session.send.reset_mock()
                try:
                    api.orders()
                except rimuapi.HumanReadableException as error:
                    assert 'Invalid output format' in str(error)
                else:
                    raise AssertionError('Invalid output setting must fail clearly')
                session.send.assert_not_called()
                api.output = 'json'
                assert json.loads(api.orders())['result']['about_orders'][0]['order_oid'] == 42
                session.send.assert_called_once()

            # Output preferences alone do not require credentials for public catalogs.
            (project / '.rimuhosting').write_text("RIMUHOSTING_OUTPUT = 'human'\n")
            with patch.dict(os.environ, {'RIMUHOSTING_APIKEY': ''}):
                api = rimuapi.Api()
                assert api.output == 'human' and api._key is None
            (project / '.rimuhosting').unlink()
            api = rimuapi.Api(key='offline-template-key')
            assert (api.output, api.progress, api.color, api.detail, api.is_pretty, api.wrap) == (
                'json', False, 'auto', 'short', True, False)
    finally:
        os.chdir(previous_directory)

print('Settings, template, output defaults and authentication checks passed (no API calls).')
