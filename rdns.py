#!/usr/bin/env python
import argparse
import rimuapi

class Args(object):
    def __init__(self, description="Set or clear the reverse DNS (PTR) record for a VM IP address."):
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("--order_oid", type=rimuapi.positive_int, required=True, help="VM order ID (positive integer)")
        parser.add_argument("--ip", type=str, required=False, help="IP address whose PTR record to change (default: first public IP on the VM)")
        parser.add_argument("--domain_name", type=str, required=False, help="PTR domain name; omit this option or pass an empty string to clear the record")

        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)

        if self.debug:
            rimuapi.isDebug = self.debug;

    def processArgs(self):
        rimuapi.debug("domain_name_args = " + str(self.domain_name))

    def run(self):
        self.processArgs()
        xx = rimuapi.Api()
        vm = xx.set_ptr(order_oid = self.order_oid, domain = None, ip = self.ip, domain_name = self.domain_name , output = self)
        rimuapi.debug ("updated ptr record")
        print(vm)
        return

if __name__ == '__main__':
    args = Args();
    args.run()
