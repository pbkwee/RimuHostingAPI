#!/usr/bin/env python
import argparse
import rimuapi

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="Start, stop, or restart a VM, or read its status or order information.")
        parser.add_argument("--order_oid", type=rimuapi.positive_int, required=True, help="VM order ID (positive integer)")
        parser.add_argument('action', help='Operation to perform; status and info only read information', choices=('start', 'stop', 'restart', 'status', 'info'))
        rimuapi._addOutputArgument(parser)

        parser.parse_args(namespace=self)

        if self.debug:
          rimuapi.isDebug = self.debug;

if __name__ == '__main__':
    args = Args()
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
        resp = xx.info("na.com", args.order_oid, output = args)
    else:
        raise Exception("Unrecognized action.")
    print(resp)
