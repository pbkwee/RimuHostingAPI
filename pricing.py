import argparse
import os
import json,sys
import urllib.request
from pprint import pprint
from pprint import pformat
import rimuapi
import mkvm
class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser()
        rimuapi._addOutputArgument(parser)
        
        parser.parse_args(namespace=self)
        
        if self.debug:
          rimuapi.isDebug = self.debug;
            
if __name__ == '__main__':
    #args = Args()
    args = mkvm.Args(description="Get pricing information");
    xx = rimuapi.Api()
    #resp = xx.pricing(args)
    #print(resp)
    server_json = args.processArgs()
    resp = xx.pricing2(server_json = server_json, output = args)
    print(resp)
