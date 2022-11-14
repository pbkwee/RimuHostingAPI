#!/usr/bin/env python
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
        parser.add_argument("--order_oid", type=int, help="order_oid to delete")
        rimuapi._addOutputArgument(parser)
        
        parser.parse_args(namespace=self)
        
        if self.debug:
            rimuapi.isDebug = self.debug;
            
if __name__ == '__main__':
    args = Args()
    xx = rimuapi.Api()
    resp = xx.delete("na.com", args.order_oid, output = args)
    print(resp)
