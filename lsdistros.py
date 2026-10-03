#!/usr/bin/env python3
import argparse
import rimuapi

class Args:
    def __init__(self):
        parser = argparse.ArgumentParser(description="List enabled VPS distributions, including promoted and recommended choices. No API key is required.")
        rimuapi._addOutputArgument(parser)
        parser.parse_args(namespace=self)
        if self.debug:
            rimuapi.isDebug = True

if __name__ == '__main__':
    args = Args()
    api = rimuapi.Api()
    print(api.distros(output=args))
