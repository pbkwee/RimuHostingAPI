"""Private, opt-in command logs; request bodies and authentication headers are excluded."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

from outputformat import format_human, strip_color

_command = ContextVar('rimuapi_command', default=None)


def safe_url(url):
    parsed = urlsplit(url)
    return urlunsplit(parsed._replace(netloc=parsed.netloc.rsplit('@', 1)[-1]))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _open(path, binary=False):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(descriptor, 'wb' if binary else 'w', **({} if binary else {'encoding': 'utf-8', 'errors': 'backslashreplace'}))


class _Tee:
    def __init__(self, stream, log, name):
        self.stream, self.log, self.name = stream, log, name

    def write(self, text):
        self.log.write(self.name, strip_color(text))
        return self.stream.write(text)

    def flush(self):
        self.log.flush()
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


class RunLog:
    def __init__(self, directory, command):
        directory = Path(directory).expanduser()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
        self.path = Path(tempfile.mkdtemp(prefix=command + '-' + stamp + '-', dir=directory))
        self.files = {}
        self.failed = False
        self.data = {'run_id': self.path.name, 'command': command, 'started_at': _now(), 'requests': []}
        self.console = None
        for name in ('stdout.txt', 'stderr.txt', 'summary.txt', 'meta.json'):
            self.files[name] = _open(self.path / name)
        self.write('summary.txt', 'Command: ' + command + '\nStarted: ' + self.data['started_at'] + '\n')
        self.metadata()

    def warn(self, error):
        if not self.failed:
            self.failed = True
            stream = self.console[1] if self.console else sys.stderr
            print('Warning: could not finish writing run logs in ' + str(self.path) + '.', file=stream)

    def write(self, name, text):
        if not self.failed:
            try:
                self.files[name].write(text)
            except (OSError, UnicodeError) as error:
                self.warn(error)

    def flush(self):
        if not self.failed:
            try:
                for file in self.files.values():
                    file.flush()
            except OSError as error:
                self.warn(error)

    def metadata(self):
        if not self.failed:
            try:
                file = self.files['meta.json']
                file.seek(0)
                file.truncate()
                json.dump(self.data, file, indent=2)
                file.flush()
            except OSError as error:
                self.warn(error)

    def capture_console(self):
        self.console = (sys.stdout, sys.stderr)
        sys.stdout = _Tee(sys.stdout, self, 'stdout.txt')
        sys.stderr = _Tee(sys.stderr, self, 'stderr.txt')

    def close(self, error=None, exit_code=0):
        self.data.update(finished_at=_now(), exit_code=exit_code)
        if error:
            self.data['error'] = str(error)
            self.write('summary.txt', '\nError: ' + str(error) + '\n')
        self.metadata()
        self.flush()
        if self.console:
            sys.stdout, sys.stderr = self.console
        for file in self.files.values():
            try:
                file.close()
            except OSError as failure:
                self.warn(failure)


class RequestLog:
    def __init__(self, run, method, url, root, standalone):
        self.run, self.root, self.standalone = run, root, standalone
        url = safe_url(url)
        self.data = {'method': method, 'url': url, 'started_at': _now()}
        number = len(run.data['requests']) + 1
        self.http_name = '%03d-http.txt' % number
        self.json_name = '%03d-response.json' % number
        # Pre-create files before sending a request; a bad log directory must not hide a successful mutation.
        run.files[self.http_name] = _open(run.path / self.http_name, binary=True)
        run.files[self.json_name] = _open(run.path / self.json_name)
        run.data['requests'].append(self.data)
        run.write('summary.txt', '\nRequest %d: %s %s\n' % (number, method, url))
        run.metadata()

    def response(self, response, streaming=False):
        self.data.update(http_status=response.status_code, http_reason=response.reason)
        header = 'HTTP %s %s\n' % (response.status_code, response.reason)
        for name, value in response.headers.items():
            if name.lower() not in ('set-cookie', 'authorization', 'proxy-authorization'):
                header += name + ': ' + value + '\n'
        self.content((header + '\n').encode('utf-8', errors='backslashreplace'))
        if not streaming:
            self.content(response.content)
        self.run.metadata()

    def content(self, chunk):
        self.run.write(self.http_name, chunk)

    def capture(self, chunks):
        for chunk in chunks:
            self.content(chunk)
            yield chunk

    def progress(self, message):
        self.run.write('summary.txt', 'Progress: ' + message + '\n')
        self.run.flush()

    def result(self, body):
        self.run.write(self.json_name, json.dumps(body, indent=2, ensure_ascii=True) + '\n')
        result = body.get(self.root) if isinstance(body, dict) and self.root else body
        if isinstance(result, dict):
            for key in ('status_code', 'status_message', 'response_type'):
                if key in result:
                    self.data[key] = result[key]
        self.run.write('summary.txt', format_human(body) + '\n')

    def finish(self, error=None):
        self.data['finished_at'] = _now()
        if error:
            self.data['error'] = str(error)
            self.run.write('summary.txt', 'Request error: ' + str(error) + '\n')
        self.run.metadata()
        self.run.flush()
        if self.standalone:
            self.run.close(error, 1 if error else 0)


class CommandRun:
    def __init__(self):
        self.log = None
        self.settings_loaded = False
        self.settings = None
        self.error = None
        self.human = False
        self.color = 'auto'
        self.wrap = False

    def start(self, directory):
        if directory and self.log is None:
            name = Path(sys.argv[0]).stem
            name = ''.join(character if character.isalnum() or character in '-_' else '-' for character in name) or 'rimuapi'
            self.log = RunLog(directory, name)
            self.log.capture_console()


def current_command():
    return _command.get()


@contextmanager
def command_run():
    run = CommandRun()
    token = _command.set(run)
    error = None
    code = 0
    try:
        yield run
    except BaseException as failure:
        code = failure.code if isinstance(failure, SystemExit) and isinstance(failure.code, int) else 1
        error = run.error or (failure if code else None)
        raise
    finally:
        if run.log:
            run.log.close(error, code)
        _command.reset(token)


def request_log(directory, method, url, root):
    command = current_command()
    if command:
        command.start(directory)
        return RequestLog(command.log, method, url, root, False) if command.log else None
    if directory:
        name = (root or 'request').removesuffix('_response').replace('_', '-')
        return RequestLog(RunLog(directory, name), method, url, root, True)
    return None
