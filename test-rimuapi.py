"""Run with python3 test-rimuapi.py; HTTP transport and shell commands are mocked."""
import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
import requests
import rimuapi
import mkvm

root = Path(__file__).resolve().parent
with patch.object(rimuapi, "load_settings", return_value=None), \
        patch.dict(os.environ, {"RIMUHOSTING_BASEURL": ""}):
    api = rimuapi.Api(key="offline-test")
    assert api._base_url == "https://rimuhosting.com"
    with patch.dict(os.environ, {"RIMUHOSTING_BASEURL": "https://example.invalid"}):
        assert rimuapi.Api(key="offline-test")._base_url == "https://example.invalid"
        with patch.object(rimuapi, "load_settings", return_value=SimpleNamespace(
                RIMUHOSTING_BASEURL="https://settings.invalid")):
            assert rimuapi.Api(key="offline-test")._base_url == "https://example.invalid"
    with patch.object(rimuapi, "load_settings", return_value=SimpleNamespace(
            RIMUHOSTING_BASEURL="https://settings.invalid")):
        assert rimuapi.Api(key="offline-test")._base_url == "https://settings.invalid"

for injections in (None, [], [{"path": "/etc/example", "data_as_string": "existing"}]):
    original = {"ssh_pub_key": "offline-public-key"}
    if injections is not None:
        original["file_injection_data"] = injections
    before = deepcopy(original)
    request = api._get_create_req("example.com", original)
    assert request["file_injection_data"] == (injections or []) + [{
        "path": "/root/.ssh/authorized_keys", "data_as_string": "offline-public-key"}]
    assert original == before

for domain in ("example.com", "example.com.", "sub.example.com."):
    assert rimuapi.valid_domain_name(domain), domain
for domain in ("", ".", "example.com..", "-example.com", "example-.com"):
    assert not rimuapi.valid_domain_name(domain), domain

template = {"instantiation_options": {"domain_name": "my-server.example"},
            "vps_parameters": {"memory_mb": 4096}}
before = deepcopy(template)
with patch.object(api, "_Api__send_request", return_value=None) as send:
    api.pricing2(server_json=template)
    assert template == before
    api.create(vmargs=template)
    assert send.call_args.kwargs["data"]["new_order_request"]["instantiation_options"]["domain_name"] == "my-server.example"

orders = {"about_orders": [{}, {}, {"order_oid": 3, "domain_name": "third.example",
                                   "metadata": {"field.with.dot": "value"}}]}
response = requests.Response()
response.status_code = 200
response.headers["content-type"] = "application/json"
response._content = json.dumps({"get_orders_response": orders}).encode()
session = Mock()
session.prepare_request.side_effect = lambda request: request.prepare()
session.send.return_value = response
with patch.object(rimuapi, "Session", return_value=session):
    for pretty in (False, True):
        api.is_pretty = pretty
        result = api.orders()
        assert isinstance(result, str)
        assert json.loads(result)["result"] == orders
    api.detail = "minimal"
    assert json.loads(api.orders()) == {"about_orders": [
        {}, {}, {"order_oid": 3, "domain_name": "third.example"}]}
    api.jsonpath = '$.about_orders[2].metadata["field.with.dot"]'
    assert json.loads(api.orders()) == {"about_orders": [
        {}, {}, {"metadata": {"field.with.dot": "value"}}]}
    api.jsonpath = "$"
    assert json.loads(api.orders()) == orders
    api.detail, api.jsonpath = "short", None
    api.is_disable_calls = True
    session.send.reset_mock()
    try:
        api.change_resources(None, 1, {"disk_space_mb": 30720})
    except rimuapi.HumanReadableException as error:
        assert "disabled" in str(error).lower()
    else:
        raise AssertionError("Disabled calls must fail explicitly.")
    session.send.assert_not_called()
    api.is_disable_calls = False
    with patch.object(rimuapi, "Api", return_value=api), \
            patch.object(sys, "argv", ["mkvm.py", "--reinstall_order_oid", "1", "--is_disable_calls"]):
        args = mkvm.Args()
        try:
            args.run()
        except rimuapi.HumanReadableException as error:
            assert "disabled" in str(error).lower()
        else:
            raise AssertionError("The reinstall lookup must honor disabled calls.")
        session.send.assert_not_called()

with tempfile.TemporaryDirectory(prefix="rimuapi-shell-check-") as directory:
    temp = Path(directory)
    python = temp / "python"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$AUDIT_CALL_LOG"\nexit "${AUDIT_RETURN_CODE:-0}"\n')
    python.chmod(0o700)
    log = temp / "calls"
    env = dict(os.environ, PATH=str(temp) + os.pathsep + os.environ["PATH"],
               AUDIT_CALL_LOG=str(log), AUDIT_RETURN_CODE="0")
    env.pop("IS_DISRUPTIVE", None)
    command = ["bash", str(root / "rimuapitests.sh"), "--order_oid", "1",
               "--details", "short", "--outputs", "json"]
    for options, expected in (([], ["status", "info"]),
                              (["--is_disruptive"], ["status", "info", "start", "stop", "restart"])):
        log.write_text("")
        result = subprocess.run(command + options, cwd=temp, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        actions = [line.split()[1] if line.split()[1] != "--detail" else line.split()[5]
                   for line in log.read_text().splitlines() if line.startswith("vmctl.py ")]
        assert actions == expected, actions
    log.write_text("")
    env["AUDIT_RETURN_CODE"] = "7"
    result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert len(log.read_text().splitlines()) == 1
with patch.object(rimuapi, "Session", return_value=session):
    api.is_disable_calls = False
    response.status_code, response.reason = 200, "OK"
    for name in (None, "", "host.example"):
        with patch.object(api, "_Api__send_request", return_value=None) as send:
            api.set_ptr(1, None, None, name)
            assert send.call_args.kwargs["data"] == "domain_name=" + (name or "")
    error_cases = [
        (400, "Bad Request", "application/json", {"jaxrs_response": {
            "error_info": {"human_readable_message": "Invalid request"}}}, "Invalid request"),
        (500, "Internal Server Error", "application/json", {"jaxrs_response": {
            "error_info": {"human_readable_message": "Handled server error"}}}, "Handled server error"),
        (503, "Service Unavailable", "text/html", "<html>Upstream unavailable</html>", None),
        (502, "Bad Gateway", "application/json", "not JSON", None),
        (403, "Forbidden", "application/json", {"error_info": {
            "human_readable_message": "Access denied"}}, "Access denied"),
        (500, "Internal Server Error", "application/json", {"unexpected": 42}, None),
        (500, "Internal Server Error", "application/json", [], None),
    ]
    for status, reason, content_type, body, message in error_cases:
        response.status_code, response.reason = status, reason
        response.headers["content-type"] = content_type
        response._content = (json.dumps(body) if not isinstance(body, str) else body).encode()
        try:
            api.orders()
        except rimuapi.HumanReadableException as error:
            assert str(error).startswith("HTTP %s %s" % (status, reason)), str(error)
            if message:
                assert message in str(error), str(error)
            else:
                assert str(error) == "HTTP %s %s" % (status, reason), str(error)
        else:
            raise AssertionError("HTTP errors must not return successful output.")
    response.status_code, response.reason = 200, "OK"
    response.headers["content-type"] = "application/json"
    marker = "offline-sensitive-marker"
    response._content = json.dumps({"post_new_vps_response": {
        "about_order": {"order_oid": 1}, "password": marker}}).encode()
    with patch.object(rimuapi, "isDebug", True), contextlib.redirect_stderr(io.StringIO()) as logs:
        api.create(vmargs={"instantiation_options": {"domain_name": "example.com", "password": marker,
                                                    "cloud_config_data": marker}})
    assert marker not in logs.getvalue(), logs.getvalue()
    assert "POST" in logs.getvalue() and "HTTP status:200" in logs.getvalue()
    assert session.send.call_args.kwargs["timeout"] == (30, 3600)

for script, options in [
    ("chattrvm.py", ["--order_oid", "0"]),
    ("chattrvm.py", ["--order_oid", "1", "--memory_mb", "0"]),
    ("chattrvm.py", ["--order_oid", "1", "--disk_space_gb", "-1"]),
    ("chattrvm.py", ["--order_oid", "1", "--disk_space_2_gb", "-1"]),
    ("mkvm.py", ["--reinstall_order_oid", "0"]),
    ("mkvm.py", ["--memory_mb", "-1"]),
    ("mkvm.py", ["--disk_space_gb", "0"]),
    ("mkvm.py", ["--disk_space_2_gb", "-1"]),
    ("rdns.py", ["--order_oid", "-1"]),
    ("rmvm.py", ["--order_oid", "0"]),
    ("lsvms.py", ["--order_oid", "-1"]),
    ("vmctl.py", ["--order_oid", "1"]),
    ("vmctl.py", ["status", "--order_oid", "0"]),
    ("mksnapshot.py", []),
    ("mksnapshot.py", ["--order_oid", "0"]),
    ("mksnapshot.py", ["--order_oid", "-1"]),
    ("lsdiskimages.py", []),
    ("lsdiskimages.py", ["--order_oid", "0"]),
    ("lsdiskimages.py", ["--order_oid", "-1"]),
]:
    with patch.object(rimuapi, "Api") as clients, \
            patch.object(sys, "argv", [script] + options), contextlib.redirect_stderr(io.StringIO()):
        try:
            runpy.run_path(str(root / script), run_name="__main__")
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError("Invalid CLI arguments were accepted: " + script + str(options))
        clients.assert_not_called()

for lookup in (None, [], {}, {"result": None}, {"result": {}},
               {"result": {"about_orders": "invalid"}},
               {"result": {"about_orders": []}},
               {"result": {"about_orders": [{"order_oid": 1}, {"order_oid": 1}]}},
               {"result": {"about_orders": [{}]}},
               {"result": {"about_orders": [{"order_oid": 2}]}}):
    client = Mock()
    client.orders.return_value = json.dumps(lookup)
    with patch.object(rimuapi, "Api", return_value=client), \
            patch.object(sys, "argv", ["mkvm.py", "--reinstall_order_oid", "1"]):
        args = mkvm.Args()
        try:
            args.run()
        except rimuapi.HumanReadableException:
            pass
        else:
            raise AssertionError("Invalid reinstall lookup was accepted.")
        client.reinstall.assert_not_called()

client = Mock()
client.orders.return_value = json.dumps({"result": {"about_orders": [{"order_oid": 1}]}})
with patch.object(rimuapi, "Api", return_value=client), \
        patch.object(sys, "argv", ["mkvm.py", "--reinstall_order_oid", "1", "--disk_space_2_gb", "0"]), \
        contextlib.redirect_stdout(io.StringIO()):
    args = mkvm.Args()
    args.run()
    request = client.reinstall.call_args.args[1]
    assert request["vps_parameters"] == {"disk_space_2_mb": 0, "memory_mb": None, "disk_space_mb": None}

with tempfile.TemporaryDirectory(prefix="rimuapi-config-check-") as directory:
    config = Path(directory) / "server.json"
    config.write_text(json.dumps({"instantiation_options": {"domain_name": "example.com", "password": marker}}))
    with patch.object(rimuapi, "Api") as clients, patch.object(rimuapi, "isDebug", True), \
            patch.object(sys, "argv", ["mkvm.py", "--server_json_file", str(config)]), \
            contextlib.redirect_stderr(io.StringIO()) as logs:
        args = mkvm.Args()
        args.processArgs()
        clients.assert_not_called()
        assert marker not in logs.getvalue()


# Discovery must use server catalogs and work without an API key.
for script, path, wrapper, field, rows in [
    ("lsdistros.py", "/r/distributions", "get_distros_response", "distro_infos", [
        {"distro_code": "future.64", "distro_description": "Future distribution",
         "is_promoted": True, "is_recommended": True},
        {"distro_code": "older.64", "distro_description": "Older distribution",
         "is_promoted": False, "is_recommended": False}]),
    ("lsdcs.py", "/r/data-centers", "get_data_centers_response", "data_center_infos", [
        {"data_center_location_code": "DCTEST", "data_center_location_name": "Test city",
         "data_center_location_country_2ltr": "NZ"}]),
]:
    for catalog in (rows, []):
        body = {wrapper: {field: catalog, "human_readable_message": "Current catalog"}}
        response = requests.Response()
        response.status_code = 200
        response.headers["content-type"] = "application/json"
        response._content = json.dumps(body).encode()
        session = Mock()
        session.prepare_request.side_effect = lambda request: request.prepare()
        session.send.return_value = response
        for options, expected in [
            ([], {field: catalog}),
            (["--detail", "minimal", "--jsonpath", "$"], body[wrapper]),
            (["--output", "raw"], body),
        ]:
            with patch.object(rimuapi, "load_settings", return_value=None), \
                    patch.dict(os.environ, {"RIMUHOSTING_APIKEY": "", "RIMUHOSTING_BASEURL": "https://example.invalid"}), \
                    patch.object(rimuapi, "Session", return_value=session), \
                    patch.object(sys, "argv", [script] + options), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                runpy.run_path(str(root / script), run_name="__main__")
            assert json.loads(output.getvalue()) == expected
            request = session.send.call_args.args[0]
            assert request.method == "GET"
            assert request.url == "https://example.invalid" + path
            assert "Authorization" not in request.headers

# Snapshot creation and disk listing share the existing transport and make one request each.
images = [
    {"optional_image_id": 11, "file_name": "root.img", "label": "Main <disk>",
     "size_mb": 2048, "modified_time": {"unix_timestamp": 1900000000}, "location": "MAIN",
     "volume_reference": "a1l-ssd", "device": "xvda1", "is_block_attached": True,
     "is_listed_in_params_file": True, "is_boot_disk": True, "is_raw_device": True},
    {"optional_image_id": 12, "file_name": "root.img", "label": "Before upgrade",
     "size_mb": 2048, "modified_time": {"unix_timestamp": 1900000001}, "location": "BACKUPIMAGE",
     "volume_reference": "b2f-ssd", "device": None, "is_block_attached": False,
     "is_listed_in_params_file": False, "is_boot_disk": False, "is_raw_device": False},
    {"optional_image_id": 13, "file_name": "cloned.img", "label": None,
     "size_mb": 4096, "modified_time": None, "location": "CLONEDIMAGE"},
    {"optional_image_id": 14, "file_name": "extra.img", "label": "Extra disk",
     "size_mb": 8192, "modified_time": None, "location": "MISC"},
]
snapshot = {"post_backup_response": {
    "backup_image": images[1], "removed_disk_images": [dict(images[1], optional_image_id=10, label="Older backup")],
    "backup_messages": ["Backup completed"], "running_vps_info": {"disk_images": images},
    "human_readable_message": "VM backup completed."}}
listing = {"get_vps_status_response": {"running_vps_info": {"disk_images": images},
                                       "human_readable_message": "Current VM status"}}
with patch.object(rimuapi, "load_settings", return_value=None), \
        patch.dict(os.environ, {"RIMUHOSTING_BASEURL": "https://example.invalid"}):
    backup_api = rimuapi.Api(key="offline-snapshot-key")


def format_options(detail="short", output="json", jsonpath=None):
    return SimpleNamespace(detail=detail, output=output, jsonpath=jsonpath,
                           is_pretty=False, is_disable_calls=False)


def set_backup_response(body, status=200, reason="OK"):
    response = requests.Response()
    response.status_code, response.reason = status, reason
    response.headers["content-type"] = "application/json"
    response._content = json.dumps(body).encode()
    response.json = Mock(wraps=response.json)
    session.send.reset_mock()
    session.send.side_effect = None
    session.send.return_value = response
    return response


def assert_backup_request(method, suffix):
    assert session.send.call_count == 1, "Backup operations must not perform lookups or retries"
    request = session.send.call_args.args[0]
    assert request.method == method
    assert request.url == "https://example.invalid/r/orders/order-123456-na.com/vps" + suffix
    assert request.headers["Authorization"] == "rimuhosting apikey=offline-snapshot-key"
    assert session.send.call_args.kwargs["timeout"] == (30, 3600)
    assert session.send.call_args.kwargs["verify"] is True
    return request


session = Mock()
session.prepare_request.side_effect = lambda request: request.prepare()
with patch.object(rimuapi, "Session", return_value=session):
    for label in (None, "", 'Before <upgrade> & "check" $(echo literal)'):
        response = set_backup_response(snapshot)
        result = json.loads(backup_api.create_snapshot(123456, label))
        assert result == {"result": snapshot["post_backup_response"]}
        request = assert_backup_request("POST", "/backups")
        assert json.loads(request.body) == {"post_backup_request": {} if label is None else {"backup_name": label}}
        response.json.assert_called_once_with()

    for detail in ("minimal", "full"):
        set_backup_response(snapshot)
        result = json.loads(backup_api.create_snapshot(123456, output=format_options(detail)))
        expected = snapshot if detail == "full" else {
            key: value for key, value in snapshot["post_backup_response"].items() if key != "running_vps_info"}
        assert result == expected
        assert_backup_request("POST", "/backups")
    response = set_backup_response(snapshot)
    assert backup_api.create_snapshot(123456, output=format_options(output="raw")) == response.text
    response.json.assert_not_called()
    set_backup_response(snapshot)
    result = backup_api.create_snapshot(123456, output=format_options(output="flat"))
    assert 'result.removed_disk_images.[0].label=Older backup' in result
    set_backup_response(snapshot)
    result = json.loads(backup_api.create_snapshot(
        123456, output=format_options("minimal", jsonpath="$.removed_disk_images")))
    assert result == {"removed_disk_images": snapshot["post_backup_response"]["removed_disk_images"]}

    summary_fields = {"optional_image_id", "file_name", "label", "size_mb", "modified_time", "location"}
    for inventory in (images, []):
        body = deepcopy(listing)
        body["get_vps_status_response"]["running_vps_info"]["disk_images"] = inventory
        for detail in ("short", "minimal", "full"):
            response = set_backup_response(body)
            result = json.loads(backup_api.disk_images(123456, output=format_options(detail)))
            expected = body if detail == "full" else inventory if detail == "short" else [
                {key: value for key, value in image.items() if key in summary_fields} for image in inventory]
            assert result == expected, result
            response.json.assert_called_once_with()
            assert_backup_request("GET", "")
        for detail in ("short", "minimal"):
            set_backup_response(body)
            result = backup_api.disk_images(123456, output=format_options(detail, "flat"))
            if inventory:
                assert '[0].optional_image_id=11' in result
            else:
                assert result == "[]"
        response = set_backup_response(body)
        assert backup_api.disk_images(123456, output=format_options("minimal", "raw")) == response.text
        response.json.assert_not_called()
    set_backup_response(listing)
    result = json.loads(backup_api.disk_images(123456, output=format_options("minimal", jsonpath="$[*].optional_image_id")))
    assert result == [{"optional_image_id": image["optional_image_id"]} for image in images]

    unavailable = [{"get_vps_status_response": info} for info in (
        {}, {"running_vps_info": None}, {"running_vps_info": {}},
        {"running_vps_info": {"disk_images": None}})]
    for body in unavailable + [{}, {"get_vps_status_response": None}, None, [], "unexpected"]:
        for detail in ("short", "minimal"):
            for output in ("json", "flat"):
                set_backup_response(body)
                try:
                    backup_api.disk_images(123456, output=format_options(detail, output))
                except rimuapi.HumanReadableException as error:
                    assert "inventory is unavailable" in str(error)
                else:
                    raise AssertionError("Missing inventory was presented as a successful empty list")
                assert_backup_request("GET", "")
        for options in (format_options("full"), format_options(output="raw")):
            set_backup_response(body)
            assert json.loads(backup_api.disk_images(123456, output=options)) == body

    for script, body, method, suffix, extra in [
        ("mksnapshot.py", snapshot, "POST", "/backups", []),
        ("mksnapshot.py", snapshot, "POST", "/backups", ["--label", "Before upgrade"]),
        ("lsdiskimages.py", listing, "GET", "", []),
    ]:
        for options in ([], ["--detail", "minimal"], ["--detail", "full"],
                        ["--output", "flat"], ["--output", "raw"], ["--is_ugly"],
                        ["--detail", "minimal", "--jsonpath", "$"]):
            set_backup_response(body)
            with patch.object(rimuapi, "Api", return_value=backup_api), \
                    patch.object(sys, "argv", [script, "--order_oid", "123456"] + extra + options), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                runpy.run_path(str(root / script), run_name="__main__")
            assert output.getvalue().strip() and output.getvalue().strip() != "None"
            request = assert_backup_request(method, suffix)
            if method == "POST":
                assert json.loads(request.body)["post_backup_request"] == ({"backup_name": "Before upgrade"} if extra else {})
        session.send.reset_mock()
        with patch.object(rimuapi, "Api", return_value=backup_api), \
                patch.object(sys, "argv", [script, "--order_oid", "123456", "--is_disable_calls"]):
            try:
                runpy.run_path(str(root / script), run_name="__main__")
            except rimuapi.HumanReadableException as error:
                assert "disabled" in str(error).lower()
            else:
                raise AssertionError("Disabled CLI call was sent")
            session.send.assert_not_called()

    for operation in (backup_api.create_snapshot, backup_api.disk_images):
        for status, reason, message in [(429, "Too Many Requests", "Please wait one hour"),
                                        (500, "Internal Server Error", "Backup result could not be verified")]:
            set_backup_response({"post_backup_response": {"error_info": {"human_readable_message": message}}}, status, reason)
            try:
                operation(123456)
            except rimuapi.HumanReadableException as error:
                assert str(error) == "HTTP %s %s: %s" % (status, reason, message)
            else:
                raise AssertionError("Backup HTTP error hidden")
            assert session.send.call_count == 1
        session.send.reset_mock()
        session.send.side_effect = requests.exceptions.ReadTimeout("offline timeout")
        try:
            operation(123456)
        except requests.exceptions.ReadTimeout:
            pass
        else:
            raise AssertionError("Read timeout hidden")
        assert session.send.call_count == 1
        disabled = format_options(); disabled.is_disable_calls = True
        session.send.reset_mock()
        try:
            operation(123456, output=disabled)
        except rimuapi.HumanReadableException as error:
            assert "disabled" in str(error).lower()
        else:
            raise AssertionError("Disabled backup call was sent")
        session.send.assert_not_called()

print("API and CLI regression checks passed (no live API calls).")
