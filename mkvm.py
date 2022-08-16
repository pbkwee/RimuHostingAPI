import argparse
import os
import json,sys
import urllib.request
from pprint import pprint
from pprint import pformat
import rimuapi
#from jsonpath_rw import jsonpath, parse
import objectpath

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="Create a VM.")
        parser.add_argument("--server_json", type=str, required=False, help="Server json config file.  e.g. containing memory_mb and disk_space_gb.  per http://apidocs.rimuhosting.com/jaxbdocs/com/rimuhosting/rs/order/OSDPrepUtils.NewVPSRequest.html")
        parser.add_argument("--cloud_config", type=str, required=False, help="CoreOS cloud config file.  Requires a 'distro' of coreos.64")
        parser.add_argument("--dc_location", type=str, required=False, help="Optional data center location.  e.g. DCDALLAS, DCFRANKFURT, DCAUCKLAND")
        parser.add_argument("--debug", action="store_true", help="Show debug logging")
        parser.add_argument("--reinstall_order_oid", type=int, help="Reinstall the specified VM")
        parser.add_argument("--memory_mb", type=int, required=False, help="Optional memory size (MB) to override server json")
        parser.add_argument("--disk_space_gb", type=int, required=False, help="Optional disk size (GB) to override server json")
        parser.add_argument("--distro", type=str, required=False, help="Optional distro type to override server json")
        parser.add_argument("--domain_name", type=str, required=False, help="Optional domain name to override server json")
        
        parser.parse_args(namespace=self)
        if self.debug:
            rimuapi.isDebug = self.debug;
            
    
    def run(self):
        xx = rimuapi.Api()
        server_json = {}
        if args.server_json:
            rimuapi.debug("loading server json from " + args.server_json)
            server_json = json.load(open(args.server_json))
            rimuapi.debug("server_json loaded from file = " + str(server_json))
            
        rimuapi.debug("server json after load = " + str(server_json))
        rimuapi.debug(" hasattr server_json 'instantiation_options' " + str(hasattr(server_json, "instantiation_options")))
        rimuapi.debug(" in server_json 'instantiation_options' " + str("instantiation_options" in server_json))
        rimuapi.debug(" in server_json 'non_existant' " + str("non_existant" in server_json))
        #for i in server_json:
        #    rimuapi.debug(" i = " + i)
        #    for j in server_json[i]:
        #        rimuapi.debug(" j = " + j)
        if not "instantiation_options" in server_json:
            rimuapi.debug("setting default instantiation_options")
            server_json["instantiation_options"] = dict()
        if not "vps_parameters" in server_json:
            rimuapi.debug("setting default vps_parameters")
            server_json["vps_parameters"] = dict()
        
        rimuapi.debug("server_json = " + str(server_json))
        rimuapi.debug("vps_parameters = " + str(server_json["vps_parameters"]))
            
        if self.cloud_config:
            server_json["instantiation_options"]["cloud_config_data"] = open(args.cloud_config).read()
        if self.dc_location:
            server_json["dc_location"] = self.dc_location
        if self.domain_name:
            server_json["instantiation_options"]["domain_name"] = self.domain_name
            rimuapi.debug("domain_name = " + self.domain_name)
        if self.memory_mb:
            server_json["vps_parameters"]["memory_mb"] = self.memory_mb
        if self.disk_space_gb:
            server_json["vps_parameters"]["disk_space_mb"] = self.disk_space_gb*1024
        if self.distro:
            server_json["instantiation_options"]["distro"] = self.distro
        #print("server_json=",server_json)
        rimuapi.debug("memory_mb = " + server_json["vps_parameters"]["memory_mb"])
        
        # see if the cluster id is in the server json, else use the command line arg value
        # replace the magic $kubernetes_domain_name with the server domain name
        if args.reinstall_order_oid:
            existing = xx.orders('N', {'server_type': 'VPS', 'order_oids': args.reinstall_order_oid})
            if len(existing)==0:
                raise Exception("Could not find that server for a reinstall (" + str(args.reinstall_order_oid) + ").  Just create a new VM?")
            if len(existing)>1:
                raise Exception("Found multiple servers with this id.")
            
            rimuapi.debug("Running a reinstall on " + str(existing[0]["order_oid"]) + " " + str(existing[0]))
            
            vm = xx.reinstall(int(existing[0]["order_oid"]), server_json)
            rimuapi.debug ("reinstalled server")
            print("order_oid:" + str(vm['post_new_vps_response']['about_order']['order_oid']))
            print("primary_ip:" + str(vm['post_new_vps_response']['about_order']['allocated_ips']['primary_ip']))
            return
        #raise Exception("debug stop")
        rimuapi.debug ("creating VM...")
        rimuapi.debug ("server-json = " + pformat(server_json))
        vm = xx.create(server_json)
        rimuapi.debug ("created VM: ")
        print (pformat(vm))
        print("order_oid:" + str(vm['post_new_vps_response']['about_order']['order_oid']))
        print("primary_ip:" + str(vm['post_new_vps_response']['about_order']['allocated_ips']['primary_ip']))
                        
if __name__ == '__main__':
    args = Args();
    args.run()
