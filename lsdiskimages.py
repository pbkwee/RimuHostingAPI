#!/usr/bin/env python3
import argparse
import rimuapi


class Args:
    def __init__(self):
        parser = argparse.ArgumentParser(description="List the VM's available disk images, including mounted images and backups.")
        parser.add_argument('--order_oid', type=rimuapi.positive_int, required=True, help='VM order ID (positive integer)')
        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)
        if self.debug:
            rimuapi.isDebug = True


if __name__ == '__main__':
    args = Args()
    api = rimuapi.Api()
    print(api.disk_images(args.order_oid, output=args))
