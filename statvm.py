import argparse
import os
import json,sys
import urllib.request
from pprint import pprint
from pprint import pformat
import rimuapi

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--order_oid", type=int, help="order_oid to load")
        parser.add_argument("--debug", action="store_true", help="Show debug logging")
        parser.parse_args(namespace=self)
        if self.debug:
          rimuapi.isDebug = self.debug;
            
if __name__ == '__main__':
    args = Args()
    xx = rimuapi.Api()
    resp = xx.order(args.order_oid, "na.com")
    output = {}
    output["running_vps_info"] = resp
    print(pformat(output))