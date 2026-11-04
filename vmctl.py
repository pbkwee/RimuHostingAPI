#!/usr/bin/env python
import argparse
from pathlib import Path
import rimuapi

class Args(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="Start, stop, restart, or rescue boot a VM, or read its status or order information.")
        parser.add_argument("--order_oid", type=rimuapi.positive_int, required=True, help="VM order ID (positive integer)")
        parser.add_argument('action', help='Operation to perform; status and info only read information', choices=('start', 'stop', 'restart', 'rescueboot', 'status', 'info'))
        # pgb:rescueapi: One-off SSH keys belong only to the rescue boot operation.
        parser.add_argument('--ssh_public_key', action='append', default=[],
                            help='OpenSSH public keys for this rescue boot; repeat or separate keys with newlines')
        parser.add_argument('--ssh_public_key_file', action='append', default=[],
                            help='Read rescue public keys from a file; repeat for multiple files')
        parser.add_argument('--is_add_users_ssh_keys', action='store_true',
                            help="Also add the account's saved SSH keys to this rescue boot")
        rimuapi._addOutputArgument(parser)

        parser.parse_args(namespace=self)
        if self.action != 'rescueboot' and (self.ssh_public_key or self.ssh_public_key_file or self.is_add_users_ssh_keys):
            parser.error('SSH key options require the rescueboot action')
        for filename in self.ssh_public_key_file:
            try:
                self.ssh_public_key.append(Path(filename).read_text(encoding='utf-8'))
            except (OSError, UnicodeError) as error:
                parser.error('Cannot read SSH public key file: ' + str(error))
        if self.action == 'rescueboot' and not (any(key.strip() for key in self.ssh_public_key) or self.is_add_users_ssh_keys):
            parser.error('rescueboot requires --ssh_public_key, --ssh_public_key_file or --is_add_users_ssh_keys')

        if self.debug:
          rimuapi.isDebug = self.debug;

if __name__ == '__main__':
    with rimuapi.command():
        args = Args()
        rimuapi.debug("action = " + str(args.action))
        xx = rimuapi.Api()
        if args.action == 'start':
            resp = xx.start("na.com", args.order_oid, output = args)
        elif args.action == 'stop':
            resp = xx.stop("na.com", args.order_oid, output = args)
        elif args.action == 'restart':
            resp = xx.reboot("na.com", args.order_oid, output = args)
        elif args.action == 'rescueboot':
            resp = xx.rescue_boot(args.order_oid, ssh_public_keys=args.ssh_public_key,
                                  is_add_users_ssh_keys=args.is_add_users_ssh_keys, output=args)
        elif args.action == 'status':
            resp = xx.status("na.com", args.order_oid, output = args)
        elif args.action == 'info':
            resp = xx.info("na.com", args.order_oid, output = args)
        else:
            raise Exception("Unrecognized action.")
        print(resp)
