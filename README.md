# Rimu Hosting API

A python library to use the RimuHosting server management API.

Also includes some standalone command line tools to perform some common operations.

To install the master branch:

```
pip install rimu
```

To install this particular version (which has a few changes used with https://github.com/pbkwee/rimuhosting-k8s) first git clone this repository, then run:

```
python3 setup.py build install
```

# Environment
An API Key is required.  Get the API key from http://rimuhosting.com/cp/apikeys.jsp.  Then export RIMUHOSTING_APIKEY=xxxx (the digits only) or in ~/.rimuhosting file set:

```
RIMUHOSTING_APIKEY=xxxx
```

Other options include:

```
# output debug messages
IS_DEBUG=True
```
# Sample usage

List VMs

```
$ python lsvms.py --detail minimal
{
    "human_readable_message": "Found 4 orders",
    "about_orders": [
        {
            "location": {
                "data_center_location_code": "DCDALLAS",
                "data_center_location_name": "Dallas"
            },
            "running_state": "RUNNING",
            "deployed_state": "DEPLOYED",
            "order_description": "LaunchtimeVPSDal; Server Type: VM; Location: Dallas; 4GB memory; 8GB on SSD disk image; Data Transfer: 6GB; Host: host1317.rimuhosting.com; 74.50.53.162; Debian 11 64-bit (aka Bullseye); Control Panel: none; 21.19 USD/m",
            "order_oid": 2853299702,
            "allocated_ips": {
                "primary_ip": "74.50.53.162"
            },
            "billing_info": {
                "monthly_recurring_amt": {
                    "amt_usd": 21.19
                }
            },
            "domain_name": "laptop.deletemesoon.com"
        }
      ]
}

```

Stop a VM

```
$ python vmctl.py stop  --order_oid 2853299702 --detail minimal
{
    "human_readable_message": "laptop.deletemesoon.com stopped.",
    "request": {
        "running_state": "NOTRUNNING"
    },
    "running_vps_info": {
        "running_state": "NOTRUNNING",
        "deployed_state": "DEPLOYED",
        "pings_ok": false
    },
        "about_order": {
        "order_description": "LaunchtimeVPSDal; Server Type: VM; Location: Dallas; 4GB memory; 8GB on SSD disk image; Data Transfer: 6GB; Host: host1317.rimuhosting.com; 74.50.53.162; Debian 11 64-bit (aka Bullseye); Control Panel: none; 21.19 USD/m; VM not running (stopped on request); Not running.",
        "running_state": "NOTRUNNING",
        "order_oid": 2853299702,
        "deployed_state": "DEPLOYED",
        "location": {
            "data_center_location_code": "DCDALLAS",
            "data_center_location_name": "Dallas"
        },
        "domain_name": "laptop.deletemesoon.com",
        "billing_info": {
            "monthly_recurring_amt": {
                "amt_usd": 21.19
            }
        },
        "allocated_ips": {
            "primary_ip": "74.50.53.162"
        }
    }
}
```

Getting sample pricing:

```
$ python pricing.py  --help
usage: pricing.py [-h] [--server_json SERVER_JSON]
                  [--cloud_config CLOUD_CONFIG] [--dc_location DC_LOCATION]
                  [--reinstall_order_oid REINSTALL_ORDER_OID]
                  [--memory_mb MEMORY_MB] [--disk_space_gb DISK_SPACE_GB]
                  [--disk_space_2_gb DISK_SPACE_2_GB] [--distro DISTRO]
                  [--features FEATURES] [--domain_name DOMAIN_NAME]
                  [--is_abort_early] [--debug] [--output [{raw,json,flat}]]
                  [--detail [{minimal,short,full}]] [--is_pretty] [--is_ugly]
                  [--jsonpath JSONPATH] [--is_disable_calls]

Get pricing information.

optional arguments:
  -h, --help            show this help message and exit
  --server_json SERVER_JSON
                        Server json config file. e.g. containing memory_mb and
                        disk_space_gb. per http://apidocs.rimuhosting.com/jaxb
                        docs/com/rimuhosting/rs/order/OSDPrepUtils.NewVPSReque
                        st.html
  --cloud_config CLOUD_CONFIG
                        CoreOS cloud config file. Requires a 'distro' of
                        coreos.64
  --dc_location DC_LOCATION
                        Optional data center location. e.g. DCDALLAS,
                        DCFRANKFURT, DCAUCKLAND
  --reinstall_order_oid REINSTALL_ORDER_OID
                        Reinstall the specified VM
  --memory_mb MEMORY_MB
                        Optional memory size (MB) to override server json
  --disk_space_gb DISK_SPACE_GB
                        Optional disk size (GB) to override server json
  --disk_space_2_gb DISK_SPACE_2_GB
                        Optional disk (#2) size (GB) to override server json
  --distro DISTRO       Optional distro type to override server json
  --features FEATURES   Optional space separated features like ssd, nvme,
                        recentcpu
  --domain_name DOMAIN_NAME
                        Optional domain name to override server json
  --is_abort_early      Abort setup before it begins.
  --debug               Show debug logging
  --output [{raw,json,flat}]
                        format of output
  --detail [{minimal,short,full}]
                        amount of detail
  --is_pretty           pretty format json
  --is_ugly             leaves json formatting
  --jsonpath JSONPATH   only output these fields using an jsonpath query
  --is_disable_calls    throw an exception rather than making a call
  
$ python pricing.py  --disk_space_gb 10 --memory_mb 3192
{
    "result": {
        "monthly_recurring_amt": {
            "amt_usd": 11.11,
            "amt": 11.11,
            "currency": "CUR_USD"
        },
        "human_readable_message": "The price for 3192MB memory and 10GB disk in Dallas is 11.11 USD/month.  You need to enter billing information."
    }
}

```