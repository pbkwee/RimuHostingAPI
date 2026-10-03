#!/usr/bin/env python
import argparse
import rimuapi

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="Shut down and cancel a VM.")
        parser.add_argument("--order_oid", type=rimuapi.positive_int, required=True, help="VM order ID to cancel (positive integer)")
        rimuapi._addOutputArgument(parser)

        parser.parse_args(namespace=self)

        if self.debug:
            rimuapi.isDebug = self.debug;

if __name__ == '__main__':
    args = Args()
    xx = rimuapi.Api()
    resp = xx.delete("na.com", args.order_oid, output = args)
    print(resp)
