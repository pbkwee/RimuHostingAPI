#!/usr/bin/env python
import rimuapi
import mkvm
if __name__ == '__main__':
    args = mkvm.Args(description="Quote VM pricing without creating or reinstalling a VM.");
    xx = rimuapi.Api()
    server_json = args.processArgs()
    resp = xx.pricing2(server_json = server_json, output = args)
    print(resp)
