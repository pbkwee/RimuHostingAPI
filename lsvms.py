#!/usr/bin/env python
import argparse
import rimuapi

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="List VMs associated with the API key, with optional filters.")
        include_inactive = parser.add_mutually_exclusive_group(required=False)
        include_inactive.add_argument('--include_inactive', dest='include_inactive', action='store_true', help='Include inactive VMs in the results')
        include_inactive.add_argument('--exclude_inactive', dest='include_inactive', action='store_false', help='Exclude inactive VMs from the results')
        parser.set_defaults(feature=True)
        parser.set_defaults(include_inactive=None)
        parser.add_argument("--order_oid", type=rimuapi.positive_int, help="Filter by VM order ID (positive integer)")
        parser.add_argument("--search", help="Filter VMs using the API search text")
        rimuapi._addOutputArgument(parser)

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

    existing = xx.orders(args.include_inactive, order_filter_json, output = args)
    print(existing)
