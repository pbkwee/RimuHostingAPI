#!/usr/bin/env python
import argparse
import os
import json,sys
import rimuapi
#from jsonpath_rw import jsonpath, parse
#import objectpath

class Args(object):
    def __init__(self, description="Set a PTR record for an server's IP address.  Command is named after what needs to happen before a 'dig' can return something."):
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("--order_oid", type=int, required=True, help="Set the reverse DNS (PTR) on this server")
        parser.add_argument("--ip", type=str, required=False, help="Optional IP address to set (else first public IP on server)")
        parser.add_argument("--domain_name", type=str, required=False, help="The name to set.  Leave empty to clear the PTR record.")

        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)
        
        if self.debug:
            rimuapi.isDebug = self.debug;
            
    def processArgs(self):
        xx = rimuapi.Api()
        rimuapi.debug("domain_name_args = " + str(self.domain_name))
        
    def run(self):
        self.processArgs()
        xx = rimuapi.Api()
        vm = xx.set_ptr(order_oid = self.order_oid, domain = None, ip = self.ip, domain_name = self.domain_name , output = self)
        rimuapi.debug ("updated ptr record")
        #print("order_oid:" + str(vm['post_new_vps_response']['about_order']['order_oid']))
        #print("primary_ip:" + str(vm['post_new_vps_response']['about_order']['allocated_ips']['primary_ip']))
        print(vm)
        return

                        
if __name__ == '__main__':
    args = Args();
    args.run()
