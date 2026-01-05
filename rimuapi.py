#!/usr/bin/env python
import urllib
import os
import re
import sys
from requests import Request, Session
from warnings import catch_warnings
from pprint import pformat
#import objectpath
import jsonpath_ng
try:
    import json
except ImportError:
    import simplejson as json

isDebug=False
def debug(debugMsg):
    if isDebug:
        print(debugMsg, file=sys.stderr)
        #print(debugMsg)
        
def _addOutputArgument(parser):
    parser.add_argument("--debug", action="store_true", help="Show debug logging")
    parser.add_argument('--output', help='format of output', nargs='?', default='json', choices=('raw', 'json', 'flat'))
    parser.add_argument('--detail', help='amount of detail', nargs='?', default='short', choices=('minimal','short', 'full'))
    parser.add_argument('--is_pretty', help='pretty format json', action="store_true", default=True)
    parser.add_argument('--is_ugly', help='leaves json formatting', dest='is_pretty', action="store_false")
    parser.add_argument('--jsonpath', help='only output these fields using an jsonpath query')
    parser.add_argument('--is_disable_calls', help='throw an exception rather than making a call', action="store_true", default = False)

def sort_unique(sequence):
    import itertools
    import operator

    return itertools.imap(
        operator.itemgetter(0),
        itertools.groupby(sorted(sequence)))

def valid_domain_name(domain_name):
    import re

    if len(domain_name) > 255:
        return False
    domain_name.rstrip('.')
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in domain_name.split("."))


def load_settings(name, path=None):
    import importlib.util
    import importlib.machinery

    path = path or os.getenv('PATH')
    home_dir = os.path.expanduser('~')
    dirs = path.split(os.pathsep)
    dirs.insert(0, home_dir)
    for d in dirs:
        bin_path = os.path.join(d, name)
        if os.path.exists(bin_path):
            fn = os.path.abspath(bin_path)
            loader = importlib.machinery.SourceFileLoader("settings", fn)
            spec = importlib.util.spec_from_file_location("settings", fn, loader=loader)
            settings = importlib.util.module_from_spec(spec)
            return settings
    return None

def _flatDict(d: dict, o: dict = None):
    if o is None:
        o = {}
    for k, v in d.items():
        if type(v) is dict:
            o.update({
                k + '.' + key: value
                for key, value in _flatDict(v).items()
            })
        else:
            o[k] = v
    return o

def _flattenJSON(y):
    out = {}

    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], ("", name+".")[name != ""] + a)
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, ("", name+".")[name != ""] + "["+str(i)+"]"
                        )
                i += 1
        else:
            #out[name[:-1]] = x
            out[name] = x

    flatten(y)
    return out

#def _getSimplifiedOrder(self, order):
#    details = objectpath.Tree(order) 
#    ip = details.execute("$.allocated_ips.primary_ip")
#    #print(pformat(order))
#    
#    
#    summary = {"order_oid" : order["order_oid"]
#               , "primary_ip" : "" if ip is None else ip
#               , "domain_name" : order["domain_name"]
#               , "dc_location" : order["location"]["data_center_location_code"]
#               , "running_state" : order["running_state"]
#               , "memory_mb" : details.execute("$.vps_parameters.memory_mb")
#               , "order_description" : details.execute("$.order_description") }
#    return summary

class HumanReadableException(Exception):
    pass

class Api:
    global isDebug
    # Show debug logging
    debug = False
    output = 'json'
    detail = 'short'
    is_pretty = True
    jsonpath = None
    is_disable_calls = False
    
    simplified_order_json = '$..(pings_ok, running_state, deployed_state, order_description, amt_usd, order_oid, domain_name, primary_ip, human_readable_message, data_center_location_code, data_center_location_name)'

    #output = "flat"
    #detail = "short" 
    #is_pretty = True
    
    def __init__(self, key=None):
        global isDebug
        self._key = key
        self._base_url = 'https://rimuhosting.com'
        self._is_ssl_verify = True
        
        #self._distros = []

        if not self._key:
            self._key = os.getenv('RIMUHOSTING_APIKEY', None)
        if not self._base_url:
            self._base_url = os.getenv('RIMUHOSTING_BASEURL', None)
        settings = load_settings('.rimuhosting')
        if settings:
            if not self._key:
                self._key = settings.RIMUHOSTING_APIKEY
            if hasattr(settings, "IS_DEBUG"):
                isDebug = settings.IS_DEBUG
                if isDebug:
                    debug("Debug enabled per IS_DEBUG setting in .rimuhosting settings file.")
            if hasattr(settings, "RIMUHOSTING_BASEURL"):
                self._base_url = settings.RIMUHOSTING_BASEURL
                if isDebug:
                    debug("Base url set per RIMUHOSTING_BASEURL setting in .rimuhosting settings file to " + str(self._base_url))
            if hasattr(settings, "RIMUHOSTING_ISVERIFYSSL"):
                self._is_ssl_verify = settings.RIMUHOSTING_ISVERIFYSSL
                if isDebug:
                    debug("Verify SSL certificate per RIMUHOSTING_ISVERIFYSSL setting in .rimuhosting settings file to " + str(self._is_ssl_verify))

    def __send_request(self, url, data=None, method='GET', isKeyRequired=True, output = None
                       , json_root = None, json_keys = None
                       , jsonpath_query = None
                       ):
        if isKeyRequired and not self._key:
            raise Exception('API Key is required.  Get the API key from http://rimuhosting.com/cp/apikeys.jsp.  Then export RIMUHOSTING_APIKEY=xxxx (the digits only) or add RIMUHOSTING_APIKEY=xxxx to a ~/.rimuhosting file.')
        headers = {
            #'Content-Type': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded' if isinstance(data, str) else 'application/json',  
            'Accept': 'application/json'
        }
        if not output:
           output = self
        if not output.detail:
           output.detail = "short"
        if not output.output:
           output.output = "raw"
        if not output.is_disable_calls:
           output.is_disable_calls = False
           
        if isKeyRequired:
            headers['Authorization']= "rimuhosting apikey=%s" % self._key
        
        #url = urllib.parse.urljoin(self._base_url, url)
        url = self._base_url+url

        data = data if isinstance(data, str) else json.dumps(data)

        s = Session()
        #s.verify=self._is_ssl_verify

        req = Request(method, url,
                      data=data,
                      headers=headers
                      )
        debug("__send_request_uri:"+str(url))
        debug("__send_request_data:"+str(data))
        if output.is_disable_calls:
            # a fancy implementation could return some mocked up data
            debug("disabling call and returning nothing.")
            return None
        debug("__send_request_response>>>")
        prepped = s.prepare_request(req)
        resp = s.send(prepped, timeout=3600, verify=self._is_ssl_verify)
        debug("__send_request_result:ok:"+str(self._is_ssl_verify)+"/"+str(resp.ok)+":")
        debug(str(resp.text))
        debug("__send_request_response<<<")

        if not resp.ok:
            message = resp.text
            try: 
                #debug("error " + str(resp))
                j2 = resp.json()
                for val in j2:
                    if "error_info" in j2[val] and "human_readable_message" in j2[val]["error_info"]:
                        message = j2[val]["error_info"]["human_readable_message"]
                        raise HumanReadableException(message)
            finally:
                # no-op, just throw the original message
                True
            raise Exception(resp.status_code, resp.reason, message)
        

        #if not output.is_pretty:
        #   output.is_pretty = True

           
        if output.output == "raw":
            return resp.text

        if output.jsonpath is not None:
            jsonpath_query = output.jsonpath
        #debug("json_minimal_fields: " + str(jsonpath_query))

        #debug("output:detail:"+output.detail+":output:"+output.output+":is_pretty:"+str(output.is_pretty))
        resp = resp.json();
        debug("output:" + " detail:" + str(output.detail) + " output: " + str(output.output)
               + " json_root: " + str(json_root) + " json_keys: " + str(list(json_keys))  
              + " jsonpath_query: " + str(jsonpath_query) )
        #debug("json root element for " + json_root + " " + str(resp[json_root]))
        #debug("json root element for json_root " + json_root + " json_keys " + str(json_keys))
        #debug("output0: setresponse to " + json_root + " exists? " + str(resp[json_root] is not None) + " output.detail " + output.detail)
        if output.detail != "full" and json_root is not None:
            if json_root in resp:
                resp = resp[json_root]
            else:
                resp = {}
                debug('no json_root in response for ' + json_root)
            debug("output: json_root node " + json_root + ("(no value found)" if resp is None else ""))
        
        if jsonpath_query is not None and output.detail == "minimal":
            from jsonpath_ng import jsonpath, parse
            debug("jsonpath_query  " + str(jsonpath_query))
            jsonpath_expr = parse(jsonpath_query)
            t={}
            for match in jsonpath_expr.find(resp):
                def _populate2(d: dict, match):
                    #debug("_populate0 " + str(name) + " match " + str(m.id_pseudopath) + " d " + str(d))
                    #debug("_populate0 match.id_psuedopath = " + str(match.id_pseudopath) + " val=" + str(match.value))
                    # about_orders.[0].domain_name=laptop.deletemesoon.com
                    # e.g. sample path: about_orders.[0].location.data_center_location_code
                    names = str(match.id_pseudopath).split(".")
                    i = 0
                    current = d
                    prev = None
                    indexname = None
                    while True:
                        if i>= len(names):
                            break
                        name = names[i]
                        # e.g. data_center_location_code from about_orders.[0].location.data_center_location_code
                        if i==len(names)-1:
                            current[name] = match.value
                            return
                        i=i+1
                        index = int(name.replace('[', '').replace(']','')) if name.find('[')==0 else None
                        if index is None:
                            # e.g. about_orders from data_center_location_code from about_orders.[0].location.data_center_location_code
                            #debug("current = " + name)
                            indexname = name
                            if name in current:
                                prev = current
                                current = current[name]
                                continue;
                            temp = {}
                            current[name] = temp
                            prev = current
                            current = temp
                            continue
                        # e.g. [0] from about_orders.[0].location.data_center_location_code
                        array=[]
                        if indexname in prev:
                            array = prev[indexname]
                        else:
                            prev[indexname] = array
                        #debug("populate: array type is " + str(type(array)))
                        if type(array) is dict:
                            array = []
                            prev[indexname] = array
                        temp = {}
                        if index >= len(array):
                            array.insert(index, temp)
                        else:
                            temp = array[index]
                        current = temp
                _populate2(t, match)
                #debug("response after jsonpath_expr match: " + str(t))
            resp = t
        else:
            debug("output: json_keys" + str(json_keys));
            #debug("post json_root resp = " + json.dumps(resp, indent=4))
                #debug("output1: setresponse to " + json_root)
            #debug("output0.5: a key exists? json_keys is not None " + str(json_keys is not None) +" len(keys>0) " + str(json_keys is not None and len(json_keys) > 0) + " json_keys " + str(json_keys) )
            if output.detail != "full" and json_keys is not None and len(json_keys) > 0:
                #debug("json_keys len " + str(len(json_keys)) + " keys " + str(json_keys))
                if len(json_keys) == 1:
                    #debug("output2: setting response to " + json_keys[0])
                    t = {}
                    if json_keys[0] in resp:
                        t[json_keys[0]] = resp[json_keys[0]]
                    else:
                        debug('warn: Could not find json_keys in the response ' + str(json_keys)) 
                    resp = t
                else:
                    t={}
                    t['result'] = {}
                    for key in json_keys:
                        if key in resp:
                            #debug("output3:adding response from " + key)
                            t['result'][key] = resp[key]
                        else:
                            debug('warn: Could not find json_key in the response for ' + str(key)) 
                    resp = t

        if output.output == "json":
            
            #r2 = {}
            #r2['result']= resp;
            #resp = r2;
            if output.is_pretty:
                debug("output: is_pretty") 
                #resp = pformat(resp, compact = True)
                #debug("resp prior to pretty is " + str(resp))
                resp = json.dumps(resp, indent=4)
            return resp
        
        if output.output == "flat":
            debug("output: flatten")
            #resp = _flatDict(resp)
            resp = _flattenJSON(resp)
            
            ret = []
            for k, v in resp.items():
                ret.append(str(k) + "=" + str(v))
            ret2=None
            def _toNumString(dotted):
                #lpadded=''
                for comp in dotted.split('.'):
                    comp = comp.replace('[', '').replace(']','')
                    #debug("comp = " + comp + " dotted = " + dotted + " is digit = " + str(comp.isdigit()) + " find =" + str(comp.find('=')>-1))
                    if comp.isdigit():
                        #print('comp='+comp.zfill(12)+':::::'+dotted)
                        return comp.zfill(12)
                    if comp.find("=")>-1:
                        #return dotted
                        return ''
                    #print('comp='+comp)
                    #lpadded = lpadded + '.' +(comp.zfill(12) if comp.isdigit() else comp.lower())
                #print('lpadded='+lpadded)
                #return lpadded
                #return dotted
                return ''
            for v in sorted(ret, key = _toNumString):
                if ret2 is None:
                    ret2=v
                else:
                    ret2=ret2+'\n'+v
            ret = ret2
                
            resp = ret
            return ret
            
        
        return resp

    # list available distros
    def distros(self, output = None):
        r = self.__send_request('/r/distributions', isKeyRequired=False, output = output, json_root = 'get_distros_response', json_keys=['distro_infos'])
        return r

    def pricing2(self, output = None, server_json = {}):
        _req = self._get_create_req("notexample.com", server_json, isReinstall=False)
        payload = {'new_order_request': _req}
        r = self.__send_request('/r/pricing-plans/new-vm-pricing',
                                data=payload, method='PUT', output=output
                                , json_root='get_new_vm_pricing_response', json_keys = ['monthly_recurring_amt', 'human_readable_message']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r
    # list pricing plans & data centers
    def pricing(self, output = None):
        r = self.__send_request('/r/pricing-plans/new-vm-pricing', isKeyRequired=False, output = output
                                , json_root = 'get_new_vm_pricing_response', json_keys = ['monthly_recurring_amt', 'human_readable_message'])
        return r

#     def data_centers(self):
#         import itertools
#         try:
#             plans = self._plans
#         except AttributeError:
#             plans = self.plans()
#         dcs = []
#         lookup = {}
#         from pprint import pprint
# 
#         for i in plans:
#             i = i['offered_at_data_center']
#             if not i: 
#                 continue
#             code = i['data_center_location_code']
#             if not code:
#                 continue
#             if not code in lookup:
#                 lookup[code] = i;
#                 dcs.append(i);
#         return dcs; 

    # list of orders/servers
    def orders(self, include_inactive='N', filter={}, output = None):
        filter['include_inactive'] = include_inactive
        uri = '/r/orders;%s' % urllib.parse.urlencode(filter)
        uri = uri.replace('&', ';')
        r = self.__send_request(uri, output = output, json_root='get_orders_response'
                                , json_keys = ['about_orders', 'human_readable_message']
                                #, jsonpath_query='$.about_orders[*].(human_readable_message, order_oid, domain_name)')
                                #, jsonpath_query='$..(human_readable_message, order_oid, domain_name)')
                                #, jsonpath_query='$..(pings_ok, running_state, deployed_state, order_description, amt_usd, order_oid, domain_name, primary_ip, human_readable_message)'
                                , jsonpath_query = self.simplified_order_json
                                )
        return r
        #data = r.json()
        #debug("order search uri of " + str(uri) + " returns " + str(data))
        #debug("about orders  " + str(data['get_orders_response']['about_orders']))
        #debug("")
        #debug("about orders 0" + str(data['get_orders_response']['about_orders'][0]))
        #debug("")
        #debug("order oid=" + str(data['get_orders_response']['about_orders'][0]['order_oid']))
        #debug("")
        #oids =""
        #for i in data['get_orders_response']['about_orders']:
        #   oids=oids+str(i['order_oid'])+","
        #debug("order oids=" + oids)
        #output = {}
        #output['about_orders'] = data['get_orders_response']['about_orders']
        #return output

    def _get_create_req(self, domain=None, kwargs={}, isReinstall = False):
        _options, _params, _req = {}, {}, {}
        _req = kwargs
        if not 'instantiation_options' in _req:
            _req['instantiation_options'] = _options
        if not 'vps_parameters' in _req:
            _req['vps_parameters'] = _params
        _options = _req['instantiation_options']
        _params = _req['vps_parameters']
        if domain:
            _options['domain_name'] = domain
        #print(pformat(_options))
        # optional on reinstall
        if not isReinstall:
            if not 'domain_name' in _options:
                raise Exception(418, 'Domain name not provided')
        if 'domain_name' in _options:
            if not valid_domain_name(_options['domain_name']):
                raise Exception(418, 'Domain not valid')
        if 'password' in kwargs:
            _options['password'] = kwargs['password']
        if 'distro' in kwargs:
            _options['distro'] = kwargs['distro']
        if 'cloud_config_data' in kwargs:
            _options['cloud_config_data'] = kwargs['cloud_config_data']
        if 'control_panel' in kwargs:
            _options['control_panel'] = kwargs['control_panel']
        if 'disk_space_mb' in kwargs:
            _params['disk_space_mb'] = kwargs['disk_space_mb']
        if 'memory_mb' in kwargs:
            _params['memory_mb'] = kwargs['memory_mb']
        if 'dc_location' in kwargs:
            _req['dc_location'] = kwargs['dc_location']
        if 'meta_data' in kwargs:
            _req['meta_data'] = kwargs['meta_data']
        if 'file_injection_data' in kwargs:
            _req['file_injection_data'] = kwargs['file_injection_data']
        if 'ssh_pub_key' in kwargs:
            if not _req['file_injection_data']:
                _req['file_injection_data'] = []
            _req['file_injection_data'].append(
                {'data_as_string': kwargs['ssh_pub_key'],
                 'path': '/root/.ssh/authorized_keys'})
        return _req
    
    # create server
    def create(self, domain, output = None, **kwargs):
        _req = self._get_create_req(domain, kwargs)
        payload = {'new_order_request': _req}
        #print("dc_location=" + (_req["dc_location"] if "dc_location" in _req else ''))
        r = self.__send_request('/r/orders/new-vps', data=payload, method='POST', output = output
                                , json_root='post_new_vps_response', json_keys = ['about_order', 'human_readable_message', 'running_vps_info']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r

    def create(self, vmargs={}, output = None):
        _req = self._get_create_req(domain=None, kwargs=vmargs)
        payload = {'new_order_request': _req}
        #print("dc_location=" + (_req["dc_location"] if "dc_location" in _req else ''))
        r = self.__send_request('/r/orders/new-vps', data=payload, method='POST', output = output
                                , json_root='post_new_vps_response', json_keys = ['about_order', 'human_readable_message', 'running_vps_info']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r

    # reinstall server
    def reinstall(self, domain, order_oid, output = None, **kwargs):
        _req = self._get_create_req(domain, kwargs, isReinstall=True)
        payload = {'new_order_request': _req}
        r = self.__send_request('/r/orders/order-%s-%s/vps/reinstall' % (order_oid, domain),
                                data=payload, method='PUT', output=output
                                , json_root='post_new_vps_response', json_keys = ['about_order', 'human_readable_message', 'setup_messages', 'running_vps_info']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r

    def reinstall(self, order_oid, vmargs={}, output = None):
        _req = self._get_create_req(domain=None, kwargs=vmargs, isReinstall=True)
        payload = {'new_order_request': _req}
        r = self.__send_request('/r/orders/order-%s-%s/vps/reinstall' % (order_oid, "na.com"),
                                data=payload, method='PUT', output=output
                                , json_root='post_new_vps_response', json_keys = ['about_order', 'human_readable_message', 'running_vps_info']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r

    # check status
    def status(self, domain, order_oid, output = None):
        r = self.__send_request('/r/orders/order-%s-%s/vps' % (order_oid, domain),  output = output
                                , json_root='get_vps_status_response', json_keys = ['about_order', 'human_readable_message', 'running_vps_info']
                                #, jsonpath_query = '$.get_vps_status_response..(pings_ok, running_state, deployed_state, order_description, amt_usd, order_oid, domain_name, primary_ip)')
                                #, jsonpath_query = '$..(pings_ok, running_state, deployed_state, order_description, amt_usd, order_oid, domain_name, primary_ip, human_readable_message)'
                                , jsonpath_query = self.simplified_order_json
                                )
        
        return r
        #data = r.json()
        #output = {}
        #output["running_vps_info"] = data['get_vps_status_response']['running_vps_info']
        #if "about_order" in data['get_vps_status_response']:
        #    output["about_order"] = data['get_vps_status_response']['about_order']
        #return output
        #return data['get_vps_status_response']['running_vps_info']
        
        #return data

    def info(self, domain, order_oid, output = None):
        r = self.__send_request('/r/orders/order-%s-%s' % (order_oid, domain), output = output
                                , json_root = 'get_order_response', json_keys = ['about_order', 'human_readable_message']
                                #, jsonpath_query = '$.get_order_response.about_order.(order_oid, domain_name, allocated_ips.primary_ip)'
                                #, jsonpath_query = '$..(order_oid, domain_name, distro, human_readable_message)'
                                #, jsonpath_query = '$..(order_oid, domain_name, primary_ip, human_readable_message)'
                                #, jsonpath_query = '$..(pings_ok, running_state, deployed_state, order_description, amt_usd, order_oid, domain_name, primary_ip, human_readable_message)'
                                , jsonpath_query = self.simplified_order_json
                                )
        return r
        #data = r.json()
        #output = {}
        #output['about_order'] = data['get_order_response']['about_order'] 
        #return output

    def _get_order_oid(self, domain=None, ip=None, orders=None):
        oids = []
        if domain is None and ip is None:
            return False
        orders = orders if orders else self.orders()
        for o in orders:
            if o['domain_name'] == domain:
                oids.append(o['order_oid'])
                if ip and ip in o['allocated_ips'].itervalues():
                    return o['order_oid']
        return oids

    # cancel server
    def delete(self, domain="na.com", order_oid=0, output = None):
        if valid_domain_name(domain) and order_oid <1:
            raise Exception("Need an order id")
        if not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        else:
            r = self.__send_request('/r/orders/order-%s-%s/vps' % (order_oid, domain),
                                    method='DELETE', output=output
                                    , json_root = 'delete_server_response', json_keys = ['about_order', 'human_readable_message', 'cancel_messages']
                                    , jsonpath_query = self.simplified_order_json
                                    )
            return r

    # change state of server
    # states: RUNNING | NOTRUNNING | RESTARTING | POWERCYCLING
    def change_state(self, domain, order_oid, new_state, output = None):
        if domain is not None and not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        r = self.__send_request('/r/orders/order-%s-%s/vps/running-state' % (order_oid, domain),
                                data={'running_state_change_request': {'running_state': new_state}},
                                method='PUT', output = output
                                , json_root='put_running_state_response'
                                , json_keys = ['about_order', 'human_readable_message', 'running_vps_info']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r

    # change state of server
    # {memory_mb : xxx, disk_space_mb : xxx , disk_space_2_mb : xxx}
    def change_resources(self, domain, order_oid, running_vps_data, output = None):
        if domain is not None and not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        r = self.__send_request('/r/orders/order-%s-%s/vps/parameters' % (order_oid, domain),
                                data={'running_vps_data': running_vps_data},
                                method='PUT', output = output
                                , json_root='put_running_vps_data_response'
                                , json_keys = ['about_order', 'human_readable_message', 'resource_change_result']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r

    # set the reverse dns/ptr dns record
    # curl -H "Accept: application/json" -X PUT -d domain_name=example.com -H "Authorization: rimuhosting apikey=<secret>"  https://rimuhosting.com/r/orders/order-xxxxx-example.com/ptr;ip=127.0.0.1
    def set_ptr(self, order_oid, domain, ip, domain_name, output = None):
        if domain is not None and not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        if domain is None:
          domain='example.com'
        if ip is  None:
          ip=''
        urlencoded = urllib.parse.urlencode({'domain_name' : domain_name })
        if isDebug:
            debug("form parameters:")
            debug(urlencoded)

        r = self.__send_request('/r/orders/order-%s-%s/ptr;ip=%s' % (order_oid, domain, ip),
                                data= urlencoded,
                                method='PUT', output = output
                                , json_root='jaxrs_response'
                                , json_keys = ['human_readable_message']
                                , jsonpath_query = '$'
                                )
        return r

    def reboot(self, domain, order_oid, output = None):
        return self.change_state(domain, order_oid, 'RESTARTING', output=output)

    def powercycle(self, domain, order_oid, output = None):
        return self.change_state(domain, order_oid, 'POWERCYCLING', output=output)

    def start(self, domain, order_oid, output = None):
        return self.change_state(domain, order_oid, 'RUNNING', output=output)

    def stop(self, domain, order_oid, output = None):
        return self.change_state(domain, order_oid, 'NOTRUNNING', output=output)

    # move VPS to another host
    def move(self, domain, order_oid,
             update_dns=False,
             move_reason='',
             pricing_change_option='CHOOSE_BEST_OPTION',  # 'CHOOSE_SAME_RESOURCES' | 'CHOOSE_SAME_PRICING'
             selected_host_server_oid=None, output = None):

        if not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        r = self.__send_request('/r/orders/order-%s-%s/vps/host-server' % (order_oid, domain),
                                data={'vps_move_request': {
                                    'is_update_dns': update_dns,
                                    'move_reason': move_reason,
                                    'pricing_change_option': pricing_change_option,
                                    'selected_host_server_oid': selected_host_server_oid}},
                                method='PUT', output = output
                                , json_root='put_host_server_move_response'
                                , json_keys = ['about_order', 'human_readable_message', 'running_vps_info']
                                , jsonpath_query = self.simplified_order_json
                                )
        return r
