#!/usr/bin/env python3
import argparse
import rimuapi

class Args:
    def __init__(self):
        parser = argparse.ArgumentParser(description="List data center locations enabled for new shared VPS setups. No API key is required.")
        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)
        if self.debug:
            rimuapi.isDebug = True

if __name__ == '__main__':
    args = Args()
    api = rimuapi.Api()
    print(api.data_centers(output=args))
