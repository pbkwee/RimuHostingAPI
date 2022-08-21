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
        rimuapi._addOutputArgument(parser)
        
        parser.parse_args(namespace=self)
        
        if self.debug:
          rimuapi.isDebug = self.debug;
            
if __name__ == '__main__':
    args = Args()
    xx = rimuapi.Api()
    resp = xx.pricing(args)
    print(resp)
