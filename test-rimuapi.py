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

print("API and CLI regression checks passed (no live API calls).")
