# RimuHosting API

A Python library and command-line tools for the RimuHosting server management API.
The tools list VMs and disk images, create saved root-disk backups, quote pricing,
create or reinstall VMs, change resources, control VM state, cancel VMs, and update reverse DNS.

## Install

Use Python 3. From this checkout, create a virtual environment and install the
library and its dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

The dependencies are `requests` and `jsonpath_ng`. The installation provides the
`rimuapi` module. Run the command-line scripts from this checkout.

## Configure access

Copy the example settings file into the project directory:

```sh
cp .rimuhosting.example .rimuhosting
```

Edit `.rimuhosting` and enter the digits of your
[API key from the control panel](https://rimuhosting.com/cp/apikeys.jsp).
The example selects readable human output with progress, automatic colors,
standard detail, and pretty JSON. It saves runs in `./runlogs` and leaves debug off.
Uncomment optional settings as needed. The file uses Python syntax.
Local settings and `runlogs/` are excluded from Git.

You can also export the key:

```sh
export RIMUHOSTING_APIKEY='YOUR_API_KEY_DIGITS'
```

Settings are read from the first `.rimuhosting` found in the current directory,
home directory, or `PATH`, in that order. Use `~/.rimuhosting` for shared settings.
Environment variables override file settings for `RIMUHOSTING_APIKEY`,
`RIMUHOSTING_BASEURL`, `RIMUHOSTING_OUTPUT`, and `RIMUHOSTING_LOGDIR`.
Command-line options override the display defaults in the settings file:

| Setting | Example default | Command-line override |
| --- | --- | --- |
| `RIMUHOSTING_OUTPUT` | `'human'` | `--output json/flat/raw/human` |
| `RIMUHOSTING_PROGRESS` | `True` | `--progress` or `--no-progress` |
| `RIMUHOSTING_COLOR` | `'auto'` | `--color auto/always/never` |
| `RIMUHOSTING_WRAP` | `False` | `--wrap` or `--no-wrap` |
| `RIMUHOSTING_DETAIL` | `'short'` | `--detail minimal/short/full` |
| `RIMUHOSTING_PRETTY` | `True` | `--is_pretty` or `--is_ugly` |

Without settings, existing defaults remain: JSON, no progress, automatic color,
standard detail, and pretty JSON. `IS_DEBUG = False` keeps diagnostics quiet;
`--debug` enables them when needed.

## Commands

Run `python3 SCRIPT --help` for the full options for each command.
Replace `123456` with a VM order ID from `lsvms.py`.

| Script | Operation |
| --- | --- |
| `lsdistros.py` | List enabled distributions, including promoted and recommended choices |
| `lsdcs.py` | List data center locations enabled for new shared VPS setups |
| `lsvms.py` | List VMs and find order IDs |
| `vmctl.py` | Start, stop, restart, or read VM status and order information |
| `mksnapshot.py` | Create a saved root-disk backup and wait for the result |
| `lsdiskimages.py` | List available disk images, including mounted images and backups |
| `pricing.py` | Quote pricing without creating or reinstalling a VM |
| `mkvm.py` | Create a VM or reinstall an existing VM |
| `chattrvm.py` | Change VM memory or disk sizes |
| `rmvm.py` | Shut down and cancel a VM |
| `rdns.py` | Set or clear a reverse DNS (PTR) record |

### Find distribution and data center codes

These catalogs come from the API, so the commands show the server's current
configuration. Neither command requires an API key:

```sh
python3 lsdistros.py
python3 lsdcs.py
```

`lsdistros.py` uses `GET /r/distributions`. Each entry contains `distro_code`,
`distro_description`, `is_promoted`, and `is_recommended`. Promoted choices match
the VPS order form. Enabled distributions can also include older choices.
Use `distro_code` with `--distro` or JSON `instantiation_options.distro`.
For example, `deb13.64` selects Debian 13 (Trixie), 64-bit.

`lsdcs.py` uses `GET /r/data-centers`. Each entry contains
`data_center_location_code`, `data_center_location_name`, and
`data_center_location_country_2ltr`. Use the location code with `--dc_location`
or JSON `dc_location`. The catalog includes locations whose shared VPS hosts
are enabled for new setups. A listed location does not guarantee capacity for
every requested configuration.

### List and inspect VMs

```sh
python3 lsvms.py --detail minimal
python3 lsvms.py --order_oid 123456
python3 lsvms.py --search example.com --exclude_inactive
python3 vmctl.py status --order_oid 123456
python3 vmctl.py info --order_oid 123456 --detail full
```

`--include_inactive` and `--exclude_inactive` are mutually exclusive.
If neither option is supplied, the API determines which orders to include.

### Control VM state

The action and `--order_oid` are required. `status` and `info` only read information.
The other actions change VM state:

```sh
python3 vmctl.py start --order_oid 123456
python3 vmctl.py stop --order_oid 123456
python3 vmctl.py restart --order_oid 123456
```

### Create a snapshot and list disk images

```sh
python3 mksnapshot.py --order_oid 123456 --label 'Before upgrade'
python3 lsdiskimages.py --order_oid 123456
python3 lsdiskimages.py --order_oid 123456 --detail minimal
```

`mksnapshot.py` creates a saved backup of the VM's root disk. The backup does not
include RAM or all VM disks. The command sends one `POST /r/orders/order-ID-na.com/vps/backups`
request and waits for completion. An omitted label uses the server's default label.
Manual-backup retention can remove an older image before the new backup completes.
Shared hosts permit one manual backup per VM each hour, based on retained images.

The default snapshot output includes `backup_image`, `removed_disk_images`,
`backup_messages`, `running_vps_info`, and `human_readable_message` under `result`.
`removed_disk_images` describes confirmed removals reported by hosts that support
the removal records. An empty list does not prove that an older host removed no images.

`lsdiskimages.py` sends one `GET /r/orders/order-ID-na.com/vps` request.
The status response can reuse inventory up to five minutes old.
Extracting the disk images adds no extra host request.
The server selects usable disk images, including mounted images and backups.
The default output is the image array with all available metadata.
`--detail minimal` selects each image's ID (`optional_image_id`), filename, label,
size, modification time, and location. `--jsonpath` expressions for minimal output
start at this image array:

```sh
python3 lsdiskimages.py --order_oid 123456 --detail minimal --jsonpath '$[*].optional_image_id'
```

An empty image array means that inventory loaded with no images.
Missing or unavailable inventory raises an error in short and minimal output.
`--detail full` and `--output raw` retain the original server response for inspection.

Both commands use the existing 30-second connection and one-hour read timeouts.
The client does not retry requests. A timeout does not cancel a running backup.
If a backup request times out or fails after starting, refresh the image listing
and VM status before requesting another backup.

### Configure and quote a VM

Save the VM configuration in a JSON file, such as `server.json`:

```json
{
  "dc_location": "DCDALLAS",
  "instantiation_options": {
    "domain_name": "vm.example.com",
    "distro": "deb13.64"
  },
  "vps_parameters": {
    "memory_mb": 2048,
    "disk_space_mb": 30720
  }
}
```

The example selects Debian 13 (Trixie), 64-bit. Use `lsdistros.py` to find other
distribution codes, and `lsdcs.py` to choose an available location.
JSON disk fields use MB. Command-line disk options use GB and convert each GB to
1024 MB. For example, `--disk_space_gb 30` sends `30720` MB.

Load the file, then quote pricing or create the VM:

```sh
python3 pricing.py --server_json_file server.json
python3 mkvm.py --server_json_file server.json
```

`pricing.py` only quotes pricing. `mkvm.py` creates a VM unless
`--reinstall_order_oid` is supplied.

Configuration is applied in this order:

1. Load `--server_json_file`, if supplied.
2. Merge `--extra_server_json`, if supplied. Matching top-level fields are replaced;
   nested objects are not merged.
3. Apply explicit options such as `--memory_mb`, `--disk_space_gb`, `--dc_location`,
   `--distro`, `--domain_name`, `--features`, and `--cloud_config`.

For example, quote a larger boot disk without editing the file:

```sh
python3 pricing.py --server_json_file server.json --disk_space_gb 40
```

Pass space-separated features as one quoted argument, such as
`--features 'ssd nvme'`. `--cloud_config FILE` reads cloud-config data for a
distribution that supports it.

### Reinstall a VM

`mkvm.py --reinstall_order_oid` reinstalls the selected VM.
The script checks that the lookup returns exactly one VM with the requested order ID.

```sh
python3 mkvm.py --reinstall_order_oid 123456 --distro deb13.64
```

Reinstall retains the current data center, memory, and boot-disk size unless the
corresponding command-line option is supplied. Values for these three settings
in the JSON file do not override the current resources during reinstall.

`pricing.py` accepts the same configuration options. With `--reinstall_order_oid`,
pricing performs the lookup and prepares the same configuration, then requests a
quote. Pricing does not reinstall the VM.

`--is_abort_early` applies to `mkvm.py`. The flag stops before the create or
reinstall request. A reinstall lookup still runs. The flag does not print a preview.

### Change resources

Specify the requested total size, rather than the amount to add:

```sh
python3 chattrvm.py --order_oid 123456 --disk_space_gb 30
python3 chattrvm.py --order_oid 123456 --memory_mb 4096 --disk_space_2_gb 20
```

Order IDs, memory sizes, and boot-disk sizes must be positive integers.
Secondary-disk sizes must be zero or greater.
`chattrvm.py` supports `--disk_space_2_gb` and `--disk_space_3_gb`.
`mkvm.py` and `pricing.py` support `--disk_space_2_gb`.

`chattrvm.py` sends only the resource options supplied on the command line.
An explicit secondary-disk size of zero is sent to the API.
The API determines whether a requested resource change is permitted.

### Cancel a VM

This command shuts down and cancels the selected VM:

```sh
python3 rmvm.py --order_oid 123456
```

### Update reverse DNS

Set a PTR record for a specific IP address:

```sh
python3 rdns.py --order_oid 123456 --ip 192.0.2.10 --domain_name vm.example.com
```

If `--ip` is omitted, the API selects the VM's first public IP address.
To clear the PTR record, omit `--domain_name` or pass an empty string:

```sh
python3 rdns.py --order_oid 123456 --ip 192.0.2.10 --domain_name ''
```

## Output and diagnostics

These options are available on all Python commands:

| Option | Behavior |
| --- | --- |
| `--output json` | Format the selected response as JSON; the default unless configured otherwise |
| `--color auto/always/never` | Control colors in human output; defaults to auto |
| `--wrap` | Wrap human output to fit the terminal |
| `--no-wrap` | Keep human output rows on one line; the default |
| `--output human` | Show a readable summary of the full result |
| `--output flat` | Write the selected response as `field=value` lines |
| `--output raw` | Write the original API JSON text; ignore detail and JSONPath selection |
| `--detail short` | Return the standard fields for the command; this is the default |
| `--detail minimal` | Select summary fields with the command's JSONPath expression |
| `--detail full` | Retain the complete API response, including its response wrapper |
| `--jsonpath EXPRESSION` | Override field selection when used with `--detail minimal` |
| `--is_pretty` | Indent JSON output; this is the default |
| `--is_ugly` | Write compact JSON without indentation |
| `--debug` | Write request and response metadata to stderr, without request or response bodies |
| `--progress` | Show live progress on stderr when available |
| `--no-progress` | Disable live progress for this command |
| `--is_disable_calls` | Raise an error before sending any API request; no preview is printed |

For example, select order IDs:

```sh
python3 lsvms.py --detail minimal --jsonpath '$..order_oid' --is_ugly
```

Use `--output human` for readable results, including operation messages and useful
VM, disk-image, and pricing details. Long rows stay on one line by default.
Use `--wrap` to fit human results to the terminal, or `--no-wrap` to override
configured wrapping. Your terminal may still visually wrap long lines.
The layout remains readable without color. Use `--output json` for scripts.
Without an output setting, JSON remains the default; the example settings choose human output.

Colors follow your terminal theme. Use `--color never` to turn them off or
`--color always` to force them on. Automatic color respects `NO_COLOR` and
`TERM=dumb`, and is disabled for redirected output. Saved logs stay plain text.

For example:

```sh
python3 lsvms.py --output human
python3 mksnapshot.py --order_oid 123456 --progress --output human
```

With `--progress --output human`, a progress message can appear on stderr and
again in the final summary on stdout.

Expected failures display an explanation on stderr and exit with status 1.
Human output includes available validation details. Use `--debug` for a traceback.
Failed commands leave stdout empty. Closing a pipe or pager exits quietly.
Library callers receive exceptions to handle themselves.

HTTP errors include the status and reason. When a handled JSON error includes a
human-readable API message, the scripts preserve that message for both 4xx and
5xx responses. Other error responses fall back to the HTTP status and reason.

Connection attempts time out after 30 seconds. The read timeout is one hour to
allow long server operations. The read timeout is not a total operation deadline.

<!-- pgb:jaxrssse: Optional progress protocol and shared client options. -->
## Progress (`--progress`)

`--progress` is accepted by every command. It requests live updates when the
endpoint supports them. Otherwise the command returns its normal response,
without progress messages. The final selected output stays on stdout; live
messages go to stderr:

```sh
python3 mksnapshot.py --order_oid 123456 --progress --label 'Before upgrade' > backup.json
python3 lsvms.py --progress
```

Progress requests advertise both SSE and JSON, preferring SSE. Ordinary JSON
responses keep their existing output and error handling. Without `--progress`,
commands continue to request JSON only. The backup endpoint currently supports
live updates; other endpoints can add support without changes to their commands.

The stream starts with a `status` event containing `status_code: 202` and a
`human_readable_message`. This means the request was accepted for processing.
`progress` events contain a `message`. The terminal `result` event contains the
endpoint's normal JSON response envelope. Its `status_code` and `response_type`
are the final request outcome. The HTTP stream itself uses status 200, so HTTP
status alone does not establish the outcome. A final status 202 retains its
usual meaning: the request was accepted and further work can still be pending.

The client raises an error for a failed terminal result. If the stream disconnects
or ends without a valid result, the outcome is unknown. The client does not retry
the request. Check the operation status before repeating a change. For backups,
refresh disk images and VM status before requesting another backup.
The read timeout measures inactivity; progress heartbeats can keep a stream open
longer than one hour.

## Optional run logs

Logging is disabled by default. Set `RIMUHOSTING_LOGDIR` to enable logs for any
output format:

```sh
export RIMUHOSTING_LOGDIR='./runlogs'
python3 lsvms.py --output human
```

The example `.rimuhosting` settings enable logs in `./runlogs`. Relative paths
start from the directory where you run the command.
The environment variable overrides that setting. An explicitly empty environment
variable disables logging, including a configured settings-file path.

Each CLI run gets a private directory named after the command and UTC time,
with a unique suffix. All requests from that command share the directory.
Library calls get one directory per call.

Each directory contains:

| File | Contents |
| --- | --- |
| `stdout.txt` | CLI standard output |
| `stderr.txt` | CLI errors, diagnostics, and progress |
| `summary.txt` | Readable results, progress, and errors |
| `meta.json` | Request outcomes, errors, exit code, and timestamps |
| `001-http.txt` | First request's HTTP status, response headers, and body |
| `001-response.json` | First request's complete JSON result |

Further requests use `002-`, `003-`, and subsequent numbered files.
The JSON file remains empty when no JSON result could be decoded.
Logs exclude request headers, request bodies, authentication, and `Set-Cookie`.
Complete response bodies can still contain sensitive data. Keep run directories private.

Progress messages are saved as they arrive.

If logging cannot start, the command stops before sending a request.
If logging fails later, the command warns that logs may be incomplete.
The operation's result is still reported.

## Use the library

```python
from rimuapi import Api

api = Api()  # Uses the same environment variables and settings file.
print(api.orders())
print(api.create_snapshot(123456, label='Before upgrade'))
print(api.disk_images(123456))
```

Set `api.progress = True` to enable progress messages on stderr for every API call.
Alternatively, set `api.on_progress = callback` to receive each live message in a
shared callback. Calls that return ordinary JSON produce no progress messages.
For example:

```python
api.progress = True
print(api.create_snapshot(123456, label='Before upgrade'))
print(api.orders())
```

The return format follows `RIMUHOSTING_OUTPUT`, or JSON when unset.
Set `api.detail`, `api.output`, and `api.is_pretty` to change the output
in the same way as the command-line options.
For example, `api.output = 'human'` selects readable summaries.
Set `api.color = 'never'` to disable color.
Set `api.log_dir` to a directory path to enable logs for subsequent API calls.
Set `api.log_dir = None` to disable those logs.

## Check the scripts

The `tests/` directory contains offline regression tests for contributors using
a source checkout. Run every suite with:

```sh
python3 tests/run.py
```

The tests use synthetic data and mocked operations. They need no API key,
block network access, and do not change any servers. Run without Python
optimization so that assertions remain enabled.
To run one suite, use `python3 tests/test-progress.py`, for example.

`rimuapitests.sh` is excluded from the offline runner. It uses the live API and
requires an API key. It lists VMs and, when an order ID is supplied, reads that
VM's status and information:

```sh
bash rimuapitests.sh --order_oid 123456 --details 'minimal short' --outputs 'json flat'
```

The shell runner invokes `python`. Ensure `python` resolves to Python 3, such as
by activating the virtual environment above. The `--is_disruptive` flag also
allows the runner to start, stop, and restart the selected VM.
