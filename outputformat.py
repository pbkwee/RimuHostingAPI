"""Human summaries of API results; request bodies stay private."""

import os
import re
import shutil
import textwrap


# Our terminal renderer emits SGR only: "\x1b[1;36mResults\x1b[0m" -> "Results".
_SGR = re.compile(r'\x1b\[[0-9;]*m')


def strip_color(text):
    """Keep generated terminal accents out of console log files."""
    return _SGR.sub('', text)


def format_terminal(response, stream, color='auto'):
    """Present human results using the destination's theme and available width."""
    terminal = stream.isatty()
    use_color = color == 'always' or (color == 'auto' and terminal and
                not os.environ.get('NO_COLOR') and os.environ.get('TERM') != 'dumb')
    width = min(100, max(20, shutil.get_terminal_size(fallback=(100, 24)).columns)) if terminal else 100
    lines = format_human(response).splitlines()
    result = []
    for index, line in enumerate(lines):
        row = line.startswith('  ')
        section = index + 1 < len(lines) and lines[index + 1].startswith('  ')
        if index and not row and (index == 1 or section or lines[index - 1].startswith('  ')):
            result.append('')
        if row:
            line = '  - ' + line[2:]
        wrapped = textwrap.wrap(line, width=width, subsequent_indent='    ' if row else '  ',
                                break_long_words=False, break_on_hyphens=False)
        if use_color and wrapped and not row:
            label, separator, value = wrapped[0].partition(':')
            style = '1;36' if index == 0 else '1'
            if label in ('Error', 'Additional errors'):
                style = '1;31'
            elif label == 'Removed disk images' and value.strip() != '0':
                style = '1;33'
            wrapped[0] = '\x1b[' + style + 'm' + label + '\x1b[0m' + separator + value
        result.extend(wrapped)
    return '\n'.join(result)


def _dict(value):
    return value if isinstance(value, dict) else {}


def _text(value, limit=None):
    if isinstance(value, dict):
        value = value.get('iso_format')
    if not isinstance(value, (str, int, float, bool)):
        return ''
    text = ' '.join(''.join(c for c in str(value) if c.isprintable() or c.isspace()).split())
    return text if limit is None or len(text) <= limit else text[:limit - 3] + '...'


def _fields(data, fields):
    data = _dict(data)
    return '; '.join(label + '=' + text for key, label in fields
                     if (text := _text(data.get(key))))


_LOCATION = (('data_center_location_code', 'code'),
             ('data_center_location_name', 'city'),
             ('data_center_location_country_2ltr', 'country'))
_IMAGE = (('optional_image_id', 'ID'), ('file_name', 'file'), ('label', 'label'),
          ('size_mb', 'MiB'), ('modified_time', 'modified'), ('location', 'location'),
          ('device', 'device'), ('is_block_attached', 'attached'),
          ('is_listed_in_params_file', 'listed'), ('is_boot_disk', 'boot'),
          ('is_raw_device', 'raw'))
_MESSAGES = ('setup_messages', 'backup_messages', 'cancel_messages',
             'running_state_messages', 'move_messages', 'resource_change_messages')


def _vm(order, running=None):
    order, running = _dict(order), _dict(running)
    parts = [_fields(order, (('order_oid', 'ID'), ('domain_name', 'domain'))),
             _fields(_dict(order.get('allocated_ips')), (('primary_ip', 'IP'),)),
             _fields(running if _text(running.get('running_state')) else order,
                     (('running_state', 'state'),)),
             _fields(order.get('vps_parameters'),
                     (('memory_mb', 'RAM MiB'), ('disk_space_mb', 'disk MiB')))]
    location = _dict(order.get('location'))
    place = _text(location.get('data_center_location_code') or
                  location.get('data_center_location_name'))
    if place:
        parts.append('location=' + place)
    return _text('; '.join(part for part in parts if part), 160)


def _money(value):
    if not isinstance(value, dict):
        return _text(value)
    return (_text(value.get('symbol_amt_str')) or
            _fields(value, (('amt', 'amount'), ('currency', 'currency'), ('amt_usd', 'USD'))))


def format_human(response):
    """Summarize useful result fields without exposing request data."""
    lines = ['Results']

    def add(label, value):
        if value:
            lines.append(label + ': ' + value)

    def rows(label, values, render):
        if not isinstance(values, list):
            return
        lines.append(label + ': ' + str(len(values)))
        for value in values:
            text = render(value)
            if text:
                lines.append('  ' + text)

    def messages(data):
        for key in _MESSAGES:
            values = data.get(key)
            if isinstance(values, (str, int, float, bool)):
                values = [values]
            rows(key.replace('_', ' ').capitalize(), values, lambda v: _text(v))

    def error(value):
        if not isinstance(value, dict):
            return _text(value)
        # full_error_message can include internal diagnostics and request details.
        return _fields(value, (('error_title', 'title'), ('error_class', 'class'),
                               ('field_name', 'field'), ('human_readable_message', 'message')))

    if isinstance(response, list):
        rows('Disk images', response, lambda v: _fields(v, _IMAGE))
        return '\n'.join(lines)

    response = _dict(response)
    # JAXRS produces one named root, e.g. {"post_backup_response": {...}}.
    # Only unwrap response roots; never traverse arbitrary echoed request objects.
    roots = [value for key, value in response.items()
             if isinstance(key, str) and key.endswith('_response') and isinstance(value, dict)]
    data = roots[0] if len(roots) == 1 else response
    add('Status', _fields(data, (('status_code', 'code'), ('status_message', 'message'),
                                  ('response_type', 'type'))))
    add('Message', _text(data.get('human_readable_message')))
    add('Error', error(data.get('error_info')))
    rows('Additional errors', data.get('extended_error_infos'), error)
    messages(data)
    running = _dict(data.get('running_vps_info'))
    add('VM', _vm(data.get('about_order'), running))
    rows('VMs', data.get('about_orders'), _vm)
    add('Runtime', _fields(running, (('pings_ok', 'ping'), ('is_suspended', 'suspended'),
                                    ('deployed_state', 'deployment'), ('vps_uptime_s', 'uptime s'),
                                    ('current_kernel', 'kernel'), ('is_backup_running', 'backup running'),
                                    ('is_backups_enabled', 'backups enabled'),
                                    ('next_backup_time', 'next backup'))))
    add('Last backup', _text(running.get('last_backup_message')))
    add('Control', _fields(data, (('is_restarted', 'restarted'), ('is_pinging', 'ping'))))
    rows('Disk images', running.get('disk_images'), lambda v: _fields(v, _IMAGE))
    if isinstance(data.get('backup_image'), dict):
        lines.append('Created backup: 1')
        add('  Image', _fields(data['backup_image'], _IMAGE))
    rows('Removed disk images', data.get('removed_disk_images'), lambda v: _fields(v, _IMAGE))
    resource = _dict(data.get('resource_change_result'))
    add('Resources', _fields(resource, (('were_resources_changed', 'changed'),)))
    messages(resource)
    add('Original monthly pricing', _money(resource.get('original_pricing')))
    add('New monthly pricing', _money(resource.get('new_pricing')))
    add('Monthly pricing', _money(data.get('monthly_recurring_amt')))
    add('Data transfer', _fields(data.get('data_transfer_usage_info'),
                                (('current_months_data_transfer_usage_bytes', 'current month bytes'),
                                 ('last_months_data_transfer_usage_bytes', 'last month bytes'),
                                 ('average_daily_data_transfer_usage_bytes', 'daily average bytes'))))
    rows('Distributions', data.get('distro_infos'), lambda v: _fields(v,
         (('distro_code', 'code'), ('distro_description', 'description'),
          ('is_promoted', 'promoted'), ('is_recommended', 'recommended'))))
    rows('Data centers', data.get('data_center_infos'), lambda v: _fields(v, _LOCATION))

    def plan(value):
        value = _dict(value)
        parts = [_fields(value, (('pricing_plan_code', 'code'),
                                ('pricing_plan_description', 'description'),
                                ('minimum_memory_mb', 'RAM MiB'), ('minimum_disk_gb', 'disk GiB'),
                                ('minimum_data_transfer_allowance_gb', 'transfer GiB'))),
                 _money(value.get('monthly_recurring_amt')) or
                 _fields(value, (('monthly_recurring_fee', 'monthly fee'),)),
                 _fields(value.get('offered_at_data_center'), _LOCATION)]
        return '; '.join(part for part in parts if part)

    rows('Pricing plans', data.get('pricing_plan_infos'), plan)
    if len(lines) == 1:
        lines.append('No recognized result fields.')
    return '\n'.join(lines)
