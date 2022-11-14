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
        parser.add_argument("--order_oid", type=int, required=True, help="order_oid to stop")
        parser.add_argument('action', help='start, stop, or restart a VM', nargs='?', choices=('start', 'stop', 'restart', 'status', 'info'))
        rimuapi._addOutputArgument(parser)
        
        #subparser = parser.add_mutually_exclusive_group(required=True)
        #subparser.add_argument('start', type=str, help='Start VM', default="start")
        #subparser.add_argument('stop', type=str, help='Stop VM', default="stop")
        #subparser.add_argument('restart', type=str, help='Restart VM', default="restart")


        #subparsers = parser.add_subparsers(help='commands')
        #start_parser = subparsers.add_parser('start', help='Start VM')
        #stop_parser = subparsers.add_parser('stop', help='Stop VM')
        #restart_parser = subparsers.add_parser('restart', help='Restart VM')
        parser.parse_args(namespace=self)
        
        if self.debug:
          rimuapi.isDebug = self.debug;
            
if __name__ == '__main__':
    args = Args()
    #print("args = " + args)
    rimuapi.debug("action = " + str(args.action))
    xx = rimuapi.Api()
    if args.action == 'start':
        resp = xx.start("na.com", args.order_oid, output = args)
    elif args.action == 'stop': 
        resp = xx.stop("na.com", args.order_oid, output = args)
    elif args.action == 'restart': 
        resp = xx.reboot("na.com", args.order_oid, output = args)
    elif args.action == 'status': 
        resp = xx.status("na.com", args.order_oid, output = args)
    elif args.action == 'info': 
        #print ("pretty:"+str(args.is_pretty))
        resp = xx.info("na.com", args.order_oid, output = args)
    else: 
        raise Exception("Unrecognized action.")
    print(resp)
