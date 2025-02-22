#!/usr/bin/env python
import argparse
import os
import json,sys
import rimuapi
#from jsonpath_rw import jsonpath, parse
#import objectpath

class Args(object):
    def __init__(self, description="Create a VM."):
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("--order_oid", type=int, required=True, help="Change this VM")
        parser.add_argument("--memory_mb", type=int, required=False, help="Optional memory size (MB)")
        parser.add_argument("--disk_space_gb", type=int, required=False, help="Optional disk size (GB)")
        parser.add_argument("--disk_space_2_gb", type=int, required=False, help="Optional disk (#2) size (GB)")
        parser.add_argument("--disk_space_3_gb", type=int, required=False, help="Optional disk (#3) size (GB)")

        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)
        
        if self.debug:
            rimuapi.isDebug = self.debug;
            
    def processArgs(self):
        xx = rimuapi.Api()
        running_vps_data = {}
        if self.memory_mb:
            running_vps_data["memory_mb"] = self.memory_mb
        if self.disk_space_gb:
            running_vps_data["disk_space_mb"] = self.disk_space_gb*1000
        if self.disk_space_2_gb:
            running_vps_data["disk_space_2_mb"] = self.disk_space_2_gb*1000
        if self.disk_space_3_gb:
            running_vps_data["disk_space_3_mb"] = self.disk_space_3_gb*1000
        rimuapi.debug("running_vps_data = " + str(running_vps_data))
        return running_vps_data
        
    def run(self):
        running_vps_data = self.processArgs()
        xx = rimuapi.Api()
        vm = xx.change_resources(order_oid = self.order_oid, domain = None, running_vps_data = running_vps_data, output = self)
        rimuapi.debug ("changed resources ")
        #print("order_oid:" + str(vm['post_new_vps_response']['about_order']['order_oid']))
        #print("primary_ip:" + str(vm['post_new_vps_response']['about_order']['allocated_ips']['primary_ip']))
        print(vm)
        return

                        
if __name__ == '__main__':
    args = Args();
    args.run()
