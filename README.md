# Rimu Hosting API

A python library to use the RimuHosting server management API.

Also includes some standalone command line tools to perform some common operations.

To install the master branch:

```
pip install rimu
```

To install this particular version (which has a few changes used with https://github.com/pbkwee/rimuhosting-k8s) first git clone this repository, then run:

```
python3 setup.py build install
```

# Environment
An API Key is required.  Get the API key from http://rimuhosting.com/cp/apikeys.jsp.  Then export RIMUHOSTING_APIKEY=xxxx (the digits only) or in ~/.rimuhosting file set:

```
RIMUHOSTING_APIKEY=xxxx
```

To enable debugging, in ~/.rimuhosting set:
```
IS_DEBUG=True
```
