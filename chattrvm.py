#!/usr/bin/env python
import argparse
import rimuapi

class Args(object):
    def __init__(self, description="Change VM memory or disk sizes. Omitted resource options are not sent to the API."):
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("--order_oid", type=rimuapi.positive_int, required=True, help="VM order ID (positive integer)")
        parser.add_argument("--memory_mb", type=rimuapi.positive_int, required=False, help="Requested total memory in MB (positive integer)")
        parser.add_argument("--disk_space_gb", type=rimuapi.positive_int, required=False, help="Requested total boot-disk size in GB (positive integer, 1024 MB per GB)")
        parser.add_argument("--disk_space_2_gb", type=rimuapi.nonnegative_int, required=False, help="Requested total second-disk size in GB (zero or greater, 1024 MB per GB)")
        parser.add_argument("--disk_space_3_gb", type=rimuapi.nonnegative_int, required=False, help="Requested total third-disk size in GB (zero or greater, 1024 MB per GB)")

        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)

        if self.debug:
            rimuapi.isDebug = self.debug;

    def processArgs(self):
        running_vps_data = {}
        if self.memory_mb is not None:
            running_vps_data["memory_mb"] = self.memory_mb
        if self.disk_space_gb is not None:
            running_vps_data["disk_space_mb"] = self.disk_space_gb*1024
        if self.disk_space_2_gb is not None:
            running_vps_data["disk_space_2_mb"] = self.disk_space_2_gb*1024
        if self.disk_space_3_gb is not None:
            running_vps_data["disk_space_3_mb"] = self.disk_space_3_gb*1024
        return running_vps_data

    def run(self):
        running_vps_data = self.processArgs()
        xx = rimuapi.Api()
        vm = xx.change_resources(order_oid = self.order_oid, domain = None, running_vps_data = running_vps_data, output = self)
        rimuapi.debug ("changed resources ")
        print(vm)
        return

if __name__ == '__main__':
    args = Args();
    args.run()
