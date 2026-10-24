"""Expected command failures and pager closure stay quiet; all clients are mocked."""
from offline import ROOT
import contextlib
import io
import runpy
import sys
from unittest.mock import Mock, patch

from requests.exceptions import ConnectionError
import rimuapi

class ClosedPager(io.StringIO):
    def write(self, text):
        raise BrokenPipeError('Pager closed')


commands = {
    'lsvms.py': [], 'lsdistros.py': [], 'lsdcs.py': [],
    'lsdiskimages.py': ['--order_oid', '42'],
    'mksnapshot.py': ['--order_oid', '42'],
    'vmctl.py': ['status', '--order_oid', '42'],
    'chattrvm.py': ['--order_oid', '42', '--memory_mb', '512'],
    'rmvm.py': ['--order_oid', '42'],
    'rdns.py': ['--order_oid', '42'],
    'mkvm.py': [], 'pricing.py': [],
}
for script, arguments in commands.items():
    for error in (rimuapi.HumanReadableException('Synthetic failure'),
                  ConnectionError('Synthetic connection failure')):
        with patch.object(rimuapi, 'load_settings', return_value=None), \
                patch.object(rimuapi, 'Api', side_effect=error), \
                patch.object(rimuapi, 'isDebug', False), \
                patch.object(sys, 'argv', [script] + arguments), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            try:
                runpy.run_path(str(ROOT / script), run_name='__main__')
            except SystemExit as failure:
                assert failure.code == 1
            else:
                raise AssertionError(script + ' accepted a failed command')
        assert stdout.getvalue() == ''
        assert stderr.getvalue() == 'Error: ' + str(error) + '\n', (script, stderr.getvalue())
    with patch.object(rimuapi, 'load_settings', return_value=None), \
            patch.object(rimuapi, 'Api', side_effect=rimuapi.HumanReadableException('Debug failure')), \
            patch.object(rimuapi, 'isDebug', False), \
            patch.object(sys, 'argv', [script] + arguments + ['--debug']), \
            contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()) as stderr:
        try:
            runpy.run_path(str(ROOT / script), run_name='__main__')
        except SystemExit as failure:
            assert failure.code == 1
        else:
            raise AssertionError(script + ' accepted a failed debug command')
    assert 'Traceback (most recent call last)' in stderr.getvalue(), script
    assert 'Debug failure' in stderr.getvalue()
    with patch.object(rimuapi, 'load_settings', return_value=None), \
            patch.object(rimuapi, 'Api', return_value=Mock()), \
            patch.object(rimuapi, 'isDebug', False), \
            patch.object(sys, 'argv', [script] + arguments), \
            contextlib.redirect_stdout(ClosedPager()) as stdout, \
            contextlib.redirect_stderr(io.StringIO()) as stderr:
        runpy.run_path(str(ROOT / script), run_name='__main__')
    assert stdout.getvalue() == '' and stderr.getvalue() == '', script

print('Shared CLI error/debug/pager checks passed (no live API calls).')
