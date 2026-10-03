#!/usr/bin/env python
import argparse
import json
import rimuapi

class Args(object):
    def __init__(self, description="Create a VM, or reinstall an existing VM."):
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("--server_json_file", type=str, required=False, help="Read VM configuration from a JSON file; see README.md for the structure")
        parser.add_argument("--extra_server_json", type=str, required=False, help="Merge a JSON object into the configuration, replacing matching top-level fields")
        parser.add_argument("--cloud_config", type=str, required=False, help="Read cloud-config data from a file for a distribution that supports it")
        parser.add_argument("--dc_location", type=str, required=False, help="Data center code, such as DCDALLAS; overrides JSON configuration")
        parser.add_argument("--reinstall_order_oid", type=rimuapi.positive_int, help="Existing VM order ID (positive integer): reinstall with mkvm.py, quote with pricing.py")
        parser.add_argument("--memory_mb", type=rimuapi.positive_int, required=False, help="Memory in MB (positive integer); overrides JSON configuration")
        parser.add_argument("--disk_space_gb", type=rimuapi.positive_int, required=False, help="Boot-disk size in GB (positive integer, 1024 MB per GB); overrides JSON configuration")
        parser.add_argument("--disk_space_2_gb", type=rimuapi.nonnegative_int, required=False, help="Second-disk size in GB (zero or greater, 1024 MB per GB); overrides JSON configuration")
        parser.add_argument("--distro", type=str, required=False, help="Distribution identifier; overrides JSON configuration")
        parser.add_argument("--features", type=str, required=False, help="Space-separated features in one quoted argument, such as 'ssd nvme'")
        parser.add_argument("--domain_name", type=str, required=False, help="VM domain name; overrides JSON configuration")
        parser.add_argument('--is_abort_early', dest='is_abort_early', default=False, action='store_true', help="With mkvm.py, stop before create or reinstall; a reinstall lookup still runs")

        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)

        if self.debug:
            rimuapi.isDebug = self.debug;

    def processArgs(self):
        server_json = {}
        if self.server_json_file:
            rimuapi.debug("loading server json from " + self.server_json_file)
            with open(self.server_json_file) as source:
                server_json = json.load(source)
        if self.extra_server_json:
            extra_server_dict = json.loads(self.extra_server_json)
            server_json = { ** server_json, ** extra_server_dict }

        if not "instantiation_options" in server_json:
            server_json["instantiation_options"] = dict()
        if not "vps_parameters" in server_json:
            server_json["vps_parameters"] = dict()

        if self.cloud_config:
            with open(self.cloud_config) as source:
                server_json["instantiation_options"]["cloud_config_data"] = source.read()
        if self.dc_location:
            server_json["dc_location"] = self.dc_location
        if self.domain_name:
            server_json["instantiation_options"]["domain_name"] = self.domain_name
        if self.memory_mb is not None:
            server_json["vps_parameters"]["memory_mb"] = self.memory_mb
        if self.disk_space_gb is not None:
            server_json["vps_parameters"]["disk_space_mb"] = self.disk_space_gb*1024
        if self.disk_space_2_gb is not None:
            server_json["vps_parameters"]["disk_space_2_mb"] = self.disk_space_2_gb*1024
        if self.distro:
            server_json["instantiation_options"]["distro"] = self.distro
        if self.features:
            server_json["features"] = self.features

        if self.reinstall_order_oid:
            xx = rimuapi.Api()
            api = argparse.Namespace(output='json', detail='short', is_pretty=False,
                                     jsonpath=None, is_disable_calls=self.is_disable_calls)
            existing = json.loads(xx.orders('N', {'server_type': 'VPS', 'include_inactive': 'N',
                                                 'order_oids': self.reinstall_order_oid}, output=api))
            if not isinstance(existing, dict) or not isinstance(existing.get('result'), dict):
                raise rimuapi.HumanReadableException("Invalid response while looking up the server for reinstall.")
            orders = existing['result'].get('about_orders')
            if not isinstance(orders, list):
                raise rimuapi.HumanReadableException("Invalid server list while looking up the server for reinstall.")
            if not orders:
                raise rimuapi.HumanReadableException("Could not find that server for a reinstall (" + str(self.reinstall_order_oid) + ").")
            if len(orders) > 1:
                raise rimuapi.HumanReadableException("Found multiple servers with this id.")
            if not isinstance(orders[0], dict) or orders[0].get('order_oid') != self.reinstall_order_oid:
                raise rimuapi.HumanReadableException("The reinstall lookup returned a different or missing order ID.")
            rimuapi.debug("Matching order: " + str(orders[0]['order_oid']))
            # Retain existing primary resources unless overridden on the command line.
            if not self.dc_location:
                server_json["dc_location"] = None
            if self.memory_mb is None:
                server_json["vps_parameters"]["memory_mb"] = None
            if self.disk_space_gb is None:
                server_json["vps_parameters"]["disk_space_mb"] = None

        return server_json

    def run(self):
        server_json = self.processArgs()
        xx = rimuapi.Api()
        if self.reinstall_order_oid:
            if self.is_abort_early:
                raise Exception("aborting early")
            vm = xx.reinstall(self.reinstall_order_oid, server_json, output = self)
            rimuapi.debug ("reinstalled server")
            print(vm)
            return

        if self.is_abort_early:
            raise Exception("aborting early")
        vm = xx.create(server_json, output = self)
        rimuapi.debug ("created VM: ")
        print(vm)

if __name__ == '__main__':
    args = Args();
    args.run()
