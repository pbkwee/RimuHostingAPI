#!/usr/bin/env python
import argparse
import os
import json,sys
import urllib.request
from pprint import pprint
from pprint import pformat
import rimuapi
#from jsonpath_rw import jsonpath, parse
#import objectpath

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="Provide a listing of all servers associated with this RimuHosting API key")
        include_inactive = parser.add_mutually_exclusive_group(required=False)
        include_inactive.add_argument('--include_inactive', dest='include_inactive', action='store_true')
        include_inactive.add_argument('--exclude_inactive', dest='include_inactive', action='store_false')
        parser.set_defaults(feature=True)
        parser.set_defaults(include_inactive=None)
        parser.add_argument("--order_oid", type=int, help="order_oid to find")
        parser.add_argument("--search", help="text to find to find")
        rimuapi._addOutputArgument(parser)

        #parser.add_argument("--include-inactive", required=False, type=bool, default=True, help="include inactive VMs in the order list")
        
        parser.parse_args(namespace=self)
        
        if self.debug:
          rimuapi.isDebug = self.debug;
        

if __name__ == '__main__':
    args = Args();
    xx = rimuapi.Api()
    order_filter_json = {'server_type': 'VPS'}
    if args.order_oid:
          order_filter_json["order_oid"] = args.order_oid
    if args.search:
          order_filter_json["search"] = args.search
          #xx.order(args.order_oid)
    
    # has a cluster id, is active, is master
    existing = xx.orders(args.include_inactive, order_filter_json, output = args)
    print(existing)
