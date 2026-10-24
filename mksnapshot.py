#!/usr/bin/env python3
import argparse
import rimuapi


class Args:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Create a saved root-disk backup and wait for the result. Retention can remove an older manual backup.")
        parser.add_argument('--order_oid', type=rimuapi.positive_int, required=True, help='VM order ID (positive integer)')
        parser.add_argument('--label', help='Optional backup label')
        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)
        if self.debug:
            rimuapi.isDebug = True


if __name__ == '__main__':
    args = Args()
    api = rimuapi.Api()
    print(api.create_snapshot(args.order_oid, label=args.label, output=args))
