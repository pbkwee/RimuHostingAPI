import urllib
import os
import sys
from requests import Request, Session
from warnings import catch_warnings
from pprint import pformat

try:
    import json
except ImportError:
    import simplejson as json

isDebug=False

def debug(debugMsg):
    if isDebug:
        #print(debugMsg, file=sys.stderr)
        print(debugMsg)
        
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
    import imp

    path = path or os.getenv('PATH')
    home_dir = os.path.expanduser('~')
    dirs = path.split(os.pathsep)
    dirs.insert(0, home_dir)
    for d in dirs:
        bin_path = os.path.join(d, name)
        if os.path.exists(bin_path):
            f = open(os.path.abspath(bin_path))
            settings = imp.load_source('settings', os.path.abspath(bin_path), f)
            f.close()
            return settings
    return None


class Api:
    global isDebug
    def __init__(self, key=None):
        global isDebug
        self._key = key
        self._base_url = 'https://rimuhosting.com'
        self._distros = []

        if not self._key:
            self._key = os.getenv('RIMUHOSTING_APIKEY', None)
        settings = load_settings('.rimuhosting')
        if not self._key:
            if settings:
                self._key = settings.RIMUHOSTING_APIKEY
                if hasattr(settings, "IS_DEBUG"):
                    isDebug = settings.IS_DEBUG
                    if isDebug:
                        debug("Debug enabled per IS_DEBUG setting in settings file.")

    def __send_request(self, url, data=None, method='GET', isKeyRequired=True):
        if isKeyRequired and not self._key:
            raise Exception('API Key is required.  Get the API key from http://rimuhosting.com/cp/apikeys.jsp.  Then export RIMUHOSTING_APIKEY=xxxx (the digits only) or add RIMUHOSTING_APIKEY=xxxx to a ~/.rimuhosting file.')
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if isKeyRequired:
            headers['Authorization']= "rimuhosting apikey=%s" % self._key
        
        url = urllib.parse.urljoin(self._base_url, url)

        data = data if isinstance(data, str) else json.dumps(data)

        s = Session()
        req = Request(method, url,
                      data=data,
                      headers=headers
                      )
        prepped = s.prepare_request(req)
        resp = s.send(prepped, timeout=3600)
        #debug("__send_request_result:ok:"+str(resp.ok)+":")
        debug("__send_request_uri:"+str(url))
        debug("__send_request_response>>>")
        debug(str(resp.text))
        debug("__send_request_response<<<")
        if not resp.ok:
            message = resp.text
            try: 
                j2 = resp.json()
                for val in j2:
                  if "error_info" in j2[val] and "human_readable_message" in j2[val]["error_info"]:
                      message = j2[val]["error_info"]["human_readable_message"]
                  break
            finally:
                raise Exception(resp.status_code, resp.reason, message)
        
        return resp

    # list available distros
    def distros(self):
        r = self.__send_request('/r/distributions', isKeyRequired=False)
        data = r.json()
        self._distros = data['get_distros_response']['distro_infos']
        return self._distros

    # list pricing plans & data centers
    def plans(self):
        r = self.__send_request('/r/pricing-plans/new-vm-pricing', isKeyRequired=False)
        data = r.json()
        self._plans = data['get_pricing_plans_response']['pricing_plan_infos']
        return self._plans

    def data_centers(self):
        import itertools
        try:
            plans = self._plans
        except AttributeError:
            plans = self.plans()
        dcs = []
        lookup = {}
        from pprint import pprint

        for i in plans:
            i = i['offered_at_data_center']
            if not i: 
                continue
            code = i['data_center_location_code']
            if not code:
                continue
            if not code in lookup:
                lookup[code] = i;
                dcs.append(i);
        return dcs; 

    # list of orders/servers
    def orders(self, include_inactive='N', filter={}):
        filter['include_inactive'] = include_inactive
        uri = '/r/orders;%s' % urllib.parse.urlencode(filter)
        uri = uri.replace('&', ';')
        r = self.__send_request(uri)
        data = r.json()
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
        return data['get_orders_response']['about_orders']

    # list of orders/servers
    def order(self, order_oid, domain_name="example.com"):
        uri = '/r/orders/order-%s-%s/vps' %(order_oid, domain_name)
        r = self.__send_request(uri)
        data = r.json()
        return data['get_order_response']['about_orders']

    def _get_req(self, domain=None, kwargs={}):
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
        if not 'domain_name' in _options:
            raise Exception(418, 'Domain name not provided')
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
    def create(self, domain, **kwargs):
        _req = self._get_req(domain, kwargs)
        payload = {'new_order_request': _req}
        #print("dc_location=" + (_req["dc_location"] if "dc_location" in _req else ''))
        r = self.__send_request('/r/orders/new-vps', data=payload, method='POST')
        return r.json()

    def create(self, vmargs={}):
        _req = self._get_req(domain=None, kwargs=vmargs)
        payload = {'new_order_request': _req}
        #print("dc_location=" + (_req["dc_location"] if "dc_location" in _req else ''))
        r = self.__send_request('/r/orders/new-vps', data=payload, method='POST')
        return r.json()

    # reinstall server
    def reinstall(self, domain, order_oid, **kwargs):
        _req = self._get_req(domain, kwargs)
        payload = {'new_order_request': _req}
        r = self.__send_request('/r/orders/order-%s-%s/vps/reinstall' % (order_oid, domain),
                                data=payload, method='PUT')
        return r.json()

    def reinstall(self, order_oid, vmargs={}):
        _req = self._get_req(domain=None, kwargs=vmargs)
        payload = {'new_order_request': _req}
        r = self.__send_request('/r/orders/order-%s-%s/vps/reinstall' % (order_oid, "na.com"),
                                data=payload, method='PUT')
        return r.json()

    # check status
    def status(self, domain, order_oid):
        r = self.__send_request('/r/orders/order-%s-%s/vps' % (order_oid, domain))
        data = r.json()
        return data['get_vps_status_response']['running_vps_info']

    def info(self, domain, order_oid):
        r = self.__send_request('/r/orders/order-%s-%s' % (order_oid, domain))
        data = r.json()
        return data['get_order_response']['about_order']

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
    def delete(self, domain="na.com", order_oid=0):
        if valid_domain_name(domain) and order_oid <1:
            raise Exception("Need an order id")
        if not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        else:
            r = self.__send_request('/r/orders/order-%s-%s/vps' % (order_oid, domain),
                                    method='DELETE')
            return r.json()

    # change state of server
    # states: RUNNING | NOTRUNNING | RESTARTING | POWERCYCLING
    def change_state(self, domain, order_oid, new_state):
        if not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        r = self.__send_request('/r/orders/order-%s-%s/vps/running-state' % (order_oid, domain),
                                data={'running_state_change_request': {'running_state': new_state}},
                                method='PUT')
        return r.json()

    def reboot(self, domain, order_oid):
        return self.change_state(domain, order_oid, 'RESTARTING')

    def powercycle(self, domain, order_oid):
        return self.change_state(domain, order_oid, 'POWERCYCLING')

    def start(self, domain, order_oid):
        return self.change_state(domain, order_oid, 'RUNNING')

    def stop(self, domain, order_oid):
        return self.change_state(domain, order_oid, 'NOTRUNNING')

    # move VPS to another host
    def move(self, domain, order_oid,
             update_dns=False,
             move_reason='',
             pricing_change_option='CHOOSE_BEST_OPTION',  # 'CHOOSE_SAME_RESOURCES' | 'CHOOSE_SAME_PRICING'
             selected_host_server_oid=None):

        if not valid_domain_name(domain):
            raise Exception(418, 'Domain not valid')
        r = self.__send_request('/r/orders/order-%s-%s/vps/host-server' % (order_oid, domain),
                                data={'vps_move_request': {
                                    'is_update_dns': update_dns,
                                    'move_reason': move_reason,
                                    'pricing_change_option': pricing_change_option,
                                    'selected_host_server_oid': selected_host_server_oid}},
                                method='PUT')
        return r.json()
