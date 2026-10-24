"""Run with python3 tests/test-chattrvm.py; API calls are replaced locally."""
from offline import ROOT
import contextlib
import io
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import patch
import rimuapi

script = ROOT / "chattrvm.py"
for options, expected in [
    (["--disk_space_gb", "30"], {"disk_space_mb": 30720}),
    (["--disk_space_gb", "30", "--disk_space_2_gb", "40",
      "--disk_space_3_gb", "50", "--memory_mb", "3872"],
     {"disk_space_mb": 30720, "disk_space_2_mb": 40960,
      "disk_space_3_mb": 51200, "memory_mb": 3872}),
    ([], {}),
    (["--disk_space_2_gb", "0", "--disk_space_3_gb", "0"],
     {"disk_space_2_mb": 0, "disk_space_3_mb": 0}),
]:
    requests = []
    api = SimpleNamespace(change_resources=lambda **request: requests.append(request))
    with patch.object(rimuapi, "load_settings", return_value=None), \
            patch.object(rimuapi, "Api", return_value=api), \
            patch.object(sys, "argv", [str(script), "--order_oid", "1"] + options), \
            contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(str(script), run_name="__main__")
    assert len(requests) == 1
    assert requests[0]["running_vps_data"] == expected, requests[0]["running_vps_data"]
print("Disk conversion regression checks passed (no API calls).")
