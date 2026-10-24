"""Pure synthetic responses; never contact the API."""
from offline import ROOT
import io
import os
from unittest.mock import patch
from outputformat import format_human, format_terminal, strip_color


def render(data, root='get_vps_status_response'):
    return format_human({root: data})


order = {'order_oid': 42, 'domain_name': 'vm.example',
         'allocated_ips': {'primary_ip': '192.0.2.1'}, 'running_state': 'STOPPED',
         'vps_parameters': {'memory_mb': 512, 'disk_space_mb': 2048},
         'location': {'data_center_location_code': 'DCDALLAS'}}
image = {'optional_image_id': 7, 'file_name': 'backup.img', 'label': 'before update',
         'size_mb': 2048, 'modified_time': '2026-10-24T01:02:03Z', 'location': 'LOCAL',
         'device': 'xvda', 'is_block_attached': False, 'is_boot_disk': True}
result = render({'status_code': 200, 'status_message': 'OK', 'response_type': 'OK',
                 'human_readable_message': 'Complete', 'about_order': order,
                 'running_vps_info': {'running_state': 'RUNNING', 'disk_images': [image]}})
for expected in ('Results', 'code=200', 'message=OK', 'type=OK', 'Message: Complete',
                 'ID=42', 'vm.example', '192.0.2.1', 'state=RUNNING', 'RAM MiB=512',
                 'disk MiB=2048', 'DCDALLAS', 'Disk images: 1', 'ID=7', 'backup.img',
                 'MiB=2048', '2026-10-24T01:02:03Z', 'attached=False', 'boot=True'):
    assert expected in result, (expected, result)
assert all(len(line[4:]) <= 160 for line in result.splitlines() if line.startswith('VM: '))
assert 'VMs: 1' in render({'about_orders': [order]}, 'get_orders_response')

for key, root in (('setup_messages', 'post_new_vps_response'),
                  ('backup_messages', 'post_backup_response'),
                  ('cancel_messages', 'delete_server_response'),
                  ('running_state_messages', 'put_running_state_response'),
                  ('move_messages', 'put_host_server_move_response')):
    result = render({key: ['operation completed'], 'about_order': order}, root)
    assert 'operation completed' in result and 'ID=42' in result

result = render({'backup_image': image, 'removed_disk_images': [image]}, 'post_backup_response')
assert 'Created backup: 1' in result and 'Removed disk images: 1' in result
assert 'Disk images: 1' in format_human([image])
assert 'Disk images: 0' in format_human([])

result = render({'resource_change_result': {
    'were_resources_changed': False, 'resource_change_messages': ['Update subscription'],
    'original_pricing': {'symbol_amt_str': '$10.00'}, 'new_pricing': {'symbol_amt_str': '$12.00'}}},
    'put_running_vps_data_response')
for expected in ('changed=False', 'Update subscription', '$10.00', '$12.00'):
    assert expected in result
assert 'Monthly pricing: amount=12; currency=USD' in render(
    {'monthly_recurring_amt': {'amt': 12, 'currency': 'USD'}}, 'get_new_vm_pricing_response')
assert 'restarted=False' in render({'is_restarted': False, 'is_pinging': True})

result = render({'status_code': 400, 'response_type': 'ERROR',
                 'error_info': {'error_title': 'Bad input', 'human_readable_message': 'Try again'},
                 'extended_error_infos': [None, {'field_name': 'memory_mb',
                                               'human_readable_message': 'Too small'}]})
for expected in ('code=400', 'type=ERROR', 'Bad input', 'Try again', 'memory_mb', 'Too small'):
    assert expected in result

result = render({'distro_infos': [{'distro_code': 'debian', 'is_recommended': True}],
                 'data_center_infos': [{'data_center_location_code': 'DCDALLAS',
                                        'data_center_location_name': 'Dallas'}],
                 'pricing_plan_infos': [{'pricing_plan_code': 'S', 'minimum_memory_mb': 512,
                                         'monthly_recurring_amt': {'symbol_amt_str': '$10'}}]})
for expected in ('Distributions: 1', 'debian', 'recommended=True', 'Data centers: 1',
                 'Dallas', 'Pricing plans: 1', 'code=S', 'RAM MiB=512', '$10'):
    assert expected in result

# Unknown dictionaries must never become an accidental request/credential dump.
private = {'password': 'SECRET_PASSWORD', 'authorized_keys': 'SECRET_KEYS',
           'cloud_config_data': 'SECRET_CLOUD', 'api_key': 'SECRET_API',
           'request_body': 'SECRET_BODY'}
result = render(dict(private, about_order=dict(order, **private),
                     new_order_request=private, request=private,
                     error_info=dict(private, full_error_message='SECRET_INTERNAL'),
                     running_vps_info=dict(private, console_public_authorized_keys='SECRET_KEYS')))
assert 'SECRET' not in result

for value in (None, 7, 'unexpected', {}, [], [None, 7, private]):
    assert format_human(value).startswith('Results')
for value in (None, 'unexpected', 7, [], [None], private):
    result = render({key: value for key in ('about_order', 'about_orders', 'running_vps_info',
                    'backup_image', 'removed_disk_images', 'resource_change_result',
                    'distro_infos', 'data_center_infos', 'extended_error_infos')})
    assert result.startswith('Results')

result = render({'about_order': dict(order, domain_name='long' * 200)})
assert len(result.split('VM: ')[1]) <= 160
result = format_human([image] * 101)
assert 'Disk images: 101' in result and result.count('  ID=7;') == 101
assert '... 1 more' not in result
assert render({'about_orders': [order] * 101}).count('  ID=42;') == 101
assert render({'distro_infos': [{'distro_code': 'debian'}] * 101}).count('  code=debian') == 101
long_message = 'operation details ' * 200 + 'END'
for key in ('human_readable_message', 'backup_messages'):
    assert long_message in render({key: long_message})
assert long_message in render({'error_info': {'human_readable_message': long_message}})

result = render({'human_readable_message': 'PTR record updated'}, 'jaxrs_response')
assert 'PTR record updated' in result
assert 'Error: message=Denied' in render({'error_info': {'human_readable_message': 'Denied'}})
assert 'Message: Already canceled' in render({'human_readable_message': 'Already canceled'},
                                            'put_cancelled_response')
for key in ('setup_messages', 'backup_messages', 'cancel_messages', 'move_messages',
            'running_state_messages', 'resource_change_messages'):
    for value in (None, {}, [None, {}], 'single message'):
        assert render({key: value}).startswith('Results')
for key in ('monthly_recurring_amt', 'resource_change_result'):
    for value in (None, {}, [], [None], 0):
        assert render({key: value}).startswith('Results')
assert 'SECRET' not in render({'about_order': {'domain_name': private},
                               'backup_image': {'label': private}})
result = render({'human_readable_message': 'first\nsecond\x1b[31m'})
assert result.splitlines()[1].startswith('Message: first second')
assert '\x1b' not in result
result = render({'backup_image': {'file_name': 'root.img',
    'modified_time': {'ms_since_epoch': 1792800000000, 'iso_format': '2026-10-24T00:00:00Z'}},
    'running_vps_info': {'next_backup_time': {'iso_format': '2026-10-25T05:00:00Z'}}})
assert 'modified=2026-10-24T00:00:00Z' in result
assert 'next backup=2026-10-25T05:00:00Z' in result
# Terminal presentation stays readable without relying on a particular color scheme.
class Terminal(io.StringIO):
    def isatty(self):
        return True


terminal, pipe = Terminal(), io.StringIO()
response = {'post_backup_response': {'status_code': 200, 'human_readable_message':
    'The root disk snapshot was saved successfully before the system upgrade.',
    'backup_image': image, 'removed_disk_images': [image],
    'error_info': {'human_readable_message': 'Example validation message'}}}
with patch.dict(os.environ, {'TERM': 'xterm', 'NO_COLOR': ''}), \
        patch('outputformat.shutil.get_terminal_size', return_value=os.terminal_size((60, 24))):
    plain = format_terminal(response, terminal, 'never')
    styled = format_terminal(response, terminal)
    assert styled.startswith('\x1b[1;36mResults\x1b[0m\n')
    assert '\x1b[1;31mError\x1b[0m' in styled
    assert '\x1b[1;33mRemoved disk images\x1b[0m' in styled
    assert strip_color(styled) == plain
    assert '\x1b' not in plain and '\x1b' not in format_terminal(response, pipe)
    assert '\n\nCreated backup: 1\n  - Image: ID=7;' in plain
    assert all(len(line) <= 60 for line in plain.splitlines())
    assert all(word in plain for word in ('backup.img', '2026-10-24T01:02:03Z', 'LOCAL'))
    assert '\x1b' in format_terminal(response, pipe, 'always')
    for setting in ({'NO_COLOR': '1'}, {'TERM': 'dumb'}):
        with patch.dict(os.environ, setting):
            assert '\x1b' not in format_terminal(response, terminal)
            assert '\x1b' in format_terminal(response, terminal, 'always')
    # Hanging indents wrap text, but identifiers are never shortened to fit a terminal.
    with patch('outputformat.shutil.get_terminal_size', return_value=os.terminal_size((30, 24))):
        assert '\n    ' in format_terminal([image], terminal, 'never')
        assert 'x' * 150 in format_terminal([dict(image, file_name='x' * 150)], terminal, 'never')
    for columns in (0, 200):
        with patch('outputformat.shutil.get_terminal_size', return_value=os.terminal_size((columns, 24))):
            assert 'Results' in format_terminal(response, terminal, 'never')
assert '\x1b' not in format_human(response)
print('Human formatter and terminal presentation offline checks passed.')
