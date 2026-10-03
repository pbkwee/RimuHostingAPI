#!/bin/bash

function usage() {
echo "Run command-line checks against the live API. Requires an API key.
Lists VMs and, when --order_oid is supplied, reads VM status and information.

--order_oid ID       VM order ID for status, info, and permitted state changes
--is_disruptive      Also run start, stop, and restart on the selected VM
--details 'VALUES'  Space-separated detail levels (default: minimal short full)
--outputs 'VALUES'  Space-separated output formats (default: json flat raw)
--help              Show this help and exit
"

}
DETAILS="minimal short full"
OUTPUTS="json flat raw"
while [ -n "$1" ]; do
  case "$1" in
  --is_disruptive)
    IS_DISRUPTIVE="Y"
    ;;
  --order_oid)
    shift
    if [ -z "$1" ] ; then
      echo "Missing order_oid" >&2
      usage
      exit 1
    fi
    ORDER_OID="$1"
    ;;
  --outputs)
    shift
    if [ -z "$1" ] ; then
      echo "Missing outputs" >&2
      usage
      exit 1
    fi
    OUTPUTS="$1"
    ;;
  --details)
    shift
    if [ -z "$1" ] ; then
      echo "Missing details" >&2
      usage
      exit 1
    fi
    DETAILS="$1"
    ;;
  --help)
    usage
    exit 0
    ;;
  *)
    echo "Unrecognised command $1" >&2
    $0 --help
    exit 1
    ;;
  esac
  shift
done

ret=0
for output in $OUTPUTS; do
  for detail in $DETAILS; do
    [ $ret -ne 0 ] && break
    echo "runtest: python lsvms.py --detail $detail --output $output"  
    python lsvms.py --detail "$detail" --output "$output"
    lret=$?
    [ $lret -ne 0 ] && echo "failed." >&2
    ret=$((ret+lret))
    [ $ret -ne 0 ] && break
    #codex:deprecated start now requires --is_disruptive.
    # [ ! -z "$ORDER_OID" ] && for vmctlcommand in 'start' 'status' 'info'; do
    [ -n "$ORDER_OID" ] && for vmctlcommand in 'status' 'info'; do
      echo "runtest: python vmctl.py $vmctlcommand --order_oid $ORDER_OID --detail $detail --output $output "
      python vmctl.py "$vmctlcommand" --order_oid "$ORDER_OID" --detail "$detail" --output "$output"
      lret=$?
      [ $lret -ne 0 ] && echo "failed." >&2
      ret=$((ret+lret))
      [ $ret -ne 0 ] && break
    done
    
    [ -n "$ORDER_OID" ] && [ -n "$IS_DISRUPTIVE" ] && for vmctlcommand in 'start' 'stop' 'restart'; do
      python vmctl.py --detail "$detail" --output "$output" "$vmctlcommand" --order_oid "$ORDER_OID"
      lret=$?
      [ $lret -ne 0 ] && echo "failed." >&2
      ret=$((ret+lret))
      [ $ret -ne 0 ] && break
    done
  done
done

exit $ret
