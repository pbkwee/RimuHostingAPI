#!/bin/bash

function usage() {
echo "Run through rimuapi.py commands to get some code coverage.
--order_oid id for vmctl commands
--is_disruptive if it is ok to stop/restart 
--is_destructive if it is ok to delete/reinstall 
--details 'value1 value2', defaults to minimal short full
--outputs 'value1 value2', defaults to json flat raw

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
    python lsvms.py --detail $detail --output $output
    lret=$?
    [ $lret -ne 0 ] && echo "failed." >&2
    ret=$((ret+$lret))
    [ $ret -ne 0 ] && break
    [ ! -z "$ORDER_OID" ] && for vmctlcommand in 'start' 'status' 'info'; do
      echo "runtest: python vmctl.py $vmctlcommand --order_oid $ORDER_OID --detail $detail --output $output "
      python vmctl.py  $vmctlcommand --order_oid "$ORDER_OID" --detail $detail --output $output
      lret=$?
      [ $lret -ne 0 ] && echo "failed." >&2
      ret=$((ret+$lret))
      [ $ret -ne 0 ] && break
    done
    
    [ ! -z "$ORDER_OID" ] && [ ! -z "$IS_DISRUPTIVE" ] && for vmctlcommand in  'stop' 'restart' ; do
      python vmctl.py  --detail $detail --output $output $vmctlcommand --order_oid "$ORDER_OID"
      lret=$?
      [ $lret -ne 0 ] && echo "failed." >&2
      ret=$((ret+$lret))
      [ $ret -ne 0 ] && break
    done
  done
done

exit $ret