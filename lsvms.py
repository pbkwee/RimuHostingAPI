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
        parser = argparse.ArgumentParser(description="Provide a listing of all servers associated with this RimuHosting API key")
        include_inactive = parser.add_mutually_exclusive_group(required=False)
        include_inactive.add_argument('--include_inactive', dest='include_inactive', action='store_true')
        include_inactive.add_argument('--exclude_inactive', dest='include_inactive', action='store_false')
        parser.set_defaults(feature=True)
        parser.add_argument("--order_oid", type=int, help="order_oid to find")

        #parser.add_argument("--include-inactive", required=False, type=bool, default=True, help="include inactive VMs in the order list")
        
        parser.parse_args(namespace=self)
    def _getSimplifiedOrder(self, order):
        details = objectpath.Tree(order) 
        ip = details.execute("$.allocated_ips.primary_ip")
        #print(pformat(order))
        summary = {"order_oid" : order["order_oid"]
                   , "primary_ip" : "" if ip is None else ip
                   , "domain_name" : order["domain_name"]
                   , "dc_location" : order["location"]["data_center_location_code"], "running_state" : order["running_state"], "memory_mb" : details.execute("$.vps_parameters.memory_mb"), "order_description" : details.execute("$.order_description") }
        return summary
    

if __name__ == '__main__':
    args = Args();
    xx = rimuapi.Api()
    order_filter_json = {'server_type': 'VPS'}
    if args.order_oid:
          order_filter_json["order_oid"] = args.order_oid
          #xx.order(args.order_oid)
    
    # has a cluster id, is active, is master
    existing = xx.orders(args.include_inactive, order_filter_json)
    output = {}
    output["servers"]=[]
    for order in existing:
        output["servers"].append(args._getSimplifiedOrder(order))
    
    print(pformat(output))


