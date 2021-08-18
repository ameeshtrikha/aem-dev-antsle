#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# AEM Command Line (CLI) Toolbox

import getopt, os, sys, time
import json, random, string, tempfile
import urllib, urllib2, base64
from distutils.version import LooseVersion
import code

try:
  import xml.etree.cElementTree as ET
except ImportError:
  import xml.etree.ElementTree as ET

#if sys.version_info[0] >= 3:
  # python3
#  from urllib import parse
#else:
  # python2.x
#  import urlparse as parse

_BOUNDARY_CHARS = string.digits + string.ascii_letters

def escape_quote(s):
  return s.replace('"', '\\"')

# ===================================================================
class AuthenticatedOpener (urllib.FancyURLopener):
  def __init__(self, *args, **kwargs):
      urllib.FancyURLopener.__init__(self, *args, **kwargs)
      self.user = None
      self.password = None

  def set_credentials(self, user, password):
      self.user = user
      self.password = password

  def get_user_passwd(self, host, realm, clear_cache=0):
      return (self.user, self.password)

# ===================================================================
class DataEncoder:
  def __init__(self, data = None, files = None):
    self.parts = []
    self.headers = {}
    self.indice = 0
    self.length = 0
    if data is not None and files is None:
      bodypart = urllib.urlencode(data)
      self.parts.append(bodypart)
      self.length = len(bodypart)
      return

    boundary = ''.join(random.choice(_BOUNDARY_CHARS) for i in range(30))
    if data is not None:
      lines = []
      for name, value in data.items():
        lines.extend((
            '--{0}'.format(boundary),
            'Content-Disposition: form-data; name="{0}"'.format(escape_quote(name)),
            '',
            str(value),
        ))
      bodypart = '\r\n'.join(lines)
      self.length += len(bodypart)
      self.parts.append(bodypart)

    if files is not None:
      for name, value in files.items():
        filename = os.path.basename(value)
        self.length += os.path.getsize(value)
        mimetype = 'application/octet-stream'
        fd = open(value, mode='rb')
        lines = ['\r\n--{0}'.format(boundary),
                 'Content-Disposition: form-data; name="{0}"; filename="{1}"'.format(
                    escape_quote(name), escape_quote(filename)),
                 'Content-Type: {0}'.format(mimetype),
                 '']
        bodypart = '\r\n'.join(lines) + '\r\n'
        self.parts.append(bodypart)
        self.length += len(bodypart)
        self.parts.append(fd)

    bodypart = '\r\n--{0}--\r\n'.format(boundary)
    self.parts.append(bodypart)
    self.length += len(bodypart)

    self.headers = {
        'Content-Type': 'multipart/form-data; boundary={0}'.format(boundary),
        'Content-Length': str(self.length),
    }

  def __len__(self):
    return self.length

  def get_headers(self):
    return self.headers

  def read(self, size):
    data = ""
    if self.indice >= len(self.parts):
      return data

    current = self.parts[self.indice]
    if hasattr(current,'read'):
      data = current.read(size)
      if not data:
        self.indice = self.indice + 1
        data = self.read(size)
    else:
      data = current
      self.indice = self.indice + 1

    return data

# ===================================================================
class AEMCommand:
  """Base class for all AEM commands"""
  def __init__(self, name, port = 4502, password = "admin", hostname = 'localhost'):
    self._name = name
    self._hostname = hostname
    self._port = port
    self._admin_pwd = password

  def get_url(self):
    return 'http://{0}:{1}'.format(self._hostname, self._port)

  def curl(self, path, data = None, method = None, files = None):
    # Create the request
    encodedData = None
    headers = {}
    if data is not None or files is not None or method == 'POST':
      encodedData = DataEncoder(data, files)
      headers = encodedData.get_headers()
    req = urllib2.Request(self.get_url() + path, encodedData, headers)

    credentials = base64.b64encode('admin:{0}'.format(self._admin_pwd))
    req.add_header('Authorization', "Basic {0}".format(credentials))

    # Send the request
    try:
      resp = urllib2.urlopen(req)
      result = resp.read()
      resp.close()
      return (resp.code, result)
    except urllib2.HTTPError as e:
      return (e.code, e.read())
    except urllib2.URLError as eu:
      return (-1, eu.reason)

  def ret(self, code, msg, data = None):
    if data is not None:
      return {'code': code, 'name': self._name, 'msg': msg, 'data': data}
    else:
      return {'code': code, 'name': self._name, 'msg': msg}

  def check_is_running(self):
    time.sleep(5)
    count = 0
    while count < 60:
      try:
        resp = urllib2.urlopen("http://%s:%s/libs/granite/core/content/login.html" % (self._hostname, self._port))
        result = resp.read()
        resp.close()
        if result.find("QUICKSTART_HOMEPAGE") >= 0:
          return True
        time.sleep(5)
        count = count + 1
      except urllib2.URLError:
        count = count + 1
        time.sleep(5)
      except urllib2.HTTPError:
        count = count + 1
        time.sleep(5)
    return False

# ===================================================================
class AEMPackage(AEMCommand):
  """AEM package administration"""

  def __init__(self, name, port = 4502, password = "admin", hostname = 'localhost'):
    AEMCommand.__init__(self, name, port, password, hostname)

  def status(self):
    '''Returns the status of a given package
    '''
    if not self.check_is_running():
      return {'name': self._name, 'state': 'http_error', 'msg': "AEM not started"}

    code, result = self.curl('/crx/packmgr/service.jsp?cmd=ls')
    if code != 200:
      return {'name': self._name, 'state': 'http_error', 'msg': result}

    doc = ET.fromstring(result)
    for package in doc.findall(".//package"):
      if package.find('name').text == self._name:
        if package.find('lastUnpacked').text is None:
          state = 'uploaded'
        else:
          state = 'installed'
        return {'name': self._name,
                'state': state,
                'version': package.find('version').text,
                'group': package.find('group').text,
                'downloadName': package.find('downloadName').text,
                'installed': package.find('lastUnpacked').text,
                'modified': package.find('lastModified').text,
                'size': package.find('size').text}

    return {'name': self._name, 'state': 'not_found'}

  def delete(self, uninstall = False):
    '''Delete a given package, with optional uninstall
    '''

    status = self.status()
    if status['state'] == 'http_error':
      return self.ret(-1, "HTTP error with the AEM server - {0}".format(status['msg']))
    if status['state'] == 'not_found':
      return self.ret(0, "Package {0} not found".format(self._name))

    uninstalled = False
    if uninstall and status['state'] == 'installed':
      path = "/crx/packmgr/service/.json/etc/packages/{0}/{1}?cmd=uninstall".format(status['group'], status['downloadName'])
      code, result = self.curl(path, method='POST')
      if code != 200:
        return self.ret(-1, "HTTP error {0} uninstalling package {1} - {2}".format(code, self._name, result))
      uninstalled = True

    path = "/crx/packmgr/service/.json/etc/packages/{0}/{1}?cmd=delete".format(status['group'], status['downloadName'])
    code, result = self.curl(path, method='POST')
    if code != 200:
      return self.ret(-1, "HTTP error {0} deleting package {1} - {2}".format(code, self._name, result))

    if uninstalled:
      return self.ret(1, "Package {0} uninstalled and deleted".format(self._name))
    else:
      return self.ret(1, "Package {0} deleted".format(self._name))

  def replicate(self):
    '''Replicate a given installed package to publish instances (author only).
    '''

    status = self.status()
    if status['state'] == 'http_error':
      return self.ret(-1, "HTTP error with the AEM server - {0}".format(status['msg']))
    if status['state'] != 'installed':
      return self.ret(0, "Package {0} not installed".format(self._name))

    path = "/crx/packmgr/service/.json/etc/packages/{0}/{1}?cmd=replicate".format(status['group'], status['downloadName'])
    code, result = self.curl(path, method='POST')
    if code != 200:
      return self.ret(-1, "HTTP error {0} replicating package {1} - {2}".format(code, self._name, result))

    return self.ret(1, "Package {0} replicated".format(self._name))

  def install(self, src, force = False, replicate = False, srcusr = None, srcpwd = None):
    '''Upload and install a given package.
       If the package is already present in AEM, it is reinstalled only if the version of the new package is superior.
       If the package is already present in AEM with same or superior version, it is reinstalled only if force = True.
       Special case: If version ends with -SNAPSHOT and both src and AEM are in the same version, the package is reinstalled.
       The zip filename in the source must follow Maven rules for the version.

       Return: (code, msg), with code =
       1  = Upload & installation OK
       0  = No change, package already installed
       -1 = Error during installation
       -2 = Installed, but error during replication on publish instances
    '''

    i = src.rfind('/')
    filename = src[i + 1:]
    if not filename.endswith('.zip'):
      return self.ret(-1, "Invalid package source. Should have zip extension")

    # Extract version of the filename in the source
    snapshot = False
    i = filename.rfind('-')
    if i < 0:
      return self.ret(-1, "Invalid package source name. No version")
    version = filename[i + 1: len(filename) - 4]
    if version == 'SNAPSHOT':
      snapshot = True
      j = filename.rfind('-', 0, i - 1)
      if j < 0:
        return self.ret(-1, "Invalid package source name. No version")
      version = filename[j + 1: i] + '-SNAPSHOT'

    # Check if package already installed
    status = self.status()
    if status['state'] == 'http_error':
      return self.ret(-1, "HTTP error with the AEM server - {0}".format(status['msg']))

    # Evaluate if the package must be installed
    doInstall = False
    checkLength = False
    if status['state'] == 'not_found' or force:
      doInstall = True
    elif LooseVersion(version) > LooseVersion(status['version']):
      doInstall = True
    elif LooseVersion(version + '-SNAPSHOT') == LooseVersion(status['version']):
      doInstall = True
    elif snapshot and LooseVersion(version) == LooseVersion(status['version']):
      doInstall = True
      checkLength = True

    if not doInstall:
      return self.ret(0, "Package already installed in same or superior version")

    # Retrieve the package to install
    istemp = False
    if src.startswith('http://') or src.startswith('https://') or src.startswith('ftp://'):
      opener = AuthenticatedOpener({})
      opener.set_credentials(srcusr, srcpwd)
      fd, srcfile = tempfile.mkstemp()
      os.close(fd)
      try:
        opener.retrieve(src, srcfile)
      except Exception as e:
        os.remove(srcfile)
        return self.ret(-1, "Could not download file {0} - {1}".format(src, e.strerror))
      istemp = True
    else:
      srcfile = src
      if not os.path.isfile(srcfile):
        return self.ret(-1, "Source file does not exists")
    length = os.stat(srcfile).st_size

    if checkLength and length == long(status['size']):
      return self.ret(0, "Package already installed with same SNAPSHOT (version + length)")

    # Upload and install the package
    try:
      data = {'name': self._name,
              'force': 'true',
              'install': 'true'}
      files = {'file': srcfile}

      path = "/crx/packmgr/service.jsp"
      code, result = self.curl(path, data=data, files=files)
      if code != 200:
        return self.ret(-1, "HTTP error {0} installing package {1} - {2}".format(code, self._name, result))

      doc = ET.fromstring(result)
      response = doc.find('response')
      if response is None:
        return self.ret(-1, "Invalid response from AEM")
      status = response.find('status')
      if status.attrib['code'] != '200':
        return self.ret(-1, "Error during installation of package {0} - {1}".format(self._name, status.text))

      data = {
        'group': response.find('.//group').text,
        'version': response.find('.//version').text,
        'size': response.find('.//size').text,
        'created': response.find('.//created').text,
        'lastModified': response.find('.//lastModified').text
      }

      i = result.index("Package installed in ")
      if i > 0:
        j = result.index("ms.", i)
        delay = result[i+21:j]

        if replicate:
          replRet = self.replicate()
          if replRet['code'] < 0:
            return self.ret(-2, "Package {0} installed in {1}ms, but error during replication - {2}".format(self._name, delay, replRet['msg']), data)
          return self.ret(1, "Package {0} installed in {1}ms and replicated on publish instances".format(self._name, delay), data)

        return self.ret(1, "Package {0} installed in {1}ms".format(self._name, delay), data)
      else:
        return self.ret(-1, "Package {0} was imported but not installed".format(self._name), data)
    finally:
      if istemp:
        os.remove(srcfile)

# ===================================================================
class AEMUser(AEMCommand):
  """AEM user administration"""

  def __init__(self, name, port = 4502, password = "admin", hostname = 'localhost'):
    AEMCommand.__init__(self, name, port, password, hostname)
    self._path = None

  def __get_group_path(self, group):
    '''Returns the path to a given group in the AEM repository.
       If the group doesn't exist, returns None
    '''

    url = ("/bin/querybuilder.json?path=/home/groups&1_property=rep:authorizableId&" +
          "1_property.value={0}&p.limit=-1".format(group))
    code, result = self.curl(url)
    if code != 200:
      return (-1, result)

    body = json.loads(result)
    success = body["success"]
    results = body["results"]
    if not success or results != 1:
      return (0, 'Not found')
    else:
      return (1, body["hits"][0]["path"])

  def __get_user_path(self):
    '''Returns the path to a given user in the AEM repository.
       If the user doesn't exist, returns None, else the self._path property is updated.
    '''

    url = ("/bin/querybuilder.json?path=/home/users&1_property=rep:authorizableId&" +
          "1_property.value={0}&p.limit=-1".format(self._name))
    code, result = self.curl(url)
    if code != 200:
      return (-1, result)

    body = json.loads(result)
    success = body["success"]
    results = body["results"]
    if not success or results != 1:
      self._path = None
      return (0, 'Not found')
    else:
      self._path = body["hits"][0]["path"]
      return (1, self._path)

  def __create(self, password, path = None):
    '''Create a user
    '''

    if password is None:
      return (-1, "Error creating user {0}, password must be provided".format(self._name))

    data = {'createUser': self._name,
            'authorizableId': self._name,
            'rep:password': password}

    if path is not None:
      data.update({'intermediatePath': path})

    url = "/libs/granite/security/post/authorizables"
    code, result = self.curl(url, data)
    if code != 201:
      return (-1, "Error creating user {0} - {1}".format(self._name, result))

    i = result.index('<div id="Message">Created</div>')
    if i > 0:
      i = result.index('<div id="Path">', i)
      j = result.index('</div>', i)
      self._path = result[i+15:j]

      return (1, "User {0} created".format(self._name))
    else:
      return (-1, "Error creating user {0}".format(self._name))

  def create_or_update(self, password, path = None, groups = None, properties = {}):
    '''Create or update a user
    '''
    code, msg = self.__get_user_path()
    if code < 0:
      return self.ret(code, msg)

    created = False
    updated = False
    if code == 0:
      code, msg = self.__create(password, path)
      if code < 0:
        return self.ret(code, msg)
      created = True

    if groups is not None:
      code, msg = self.__set_groups(groups)
      if code < 0:
        return self.ret(-1, "Error updating groups for user user {0} - {1}".format(self._name, msg))
      updated = code > 0

    code, msg = self.__set_properties(properties)
    if code < 0:
      return self.ret(code, msg)
    elif code > 0:
      updated = True

    if created:
      return self.ret(1, "User {0} created in path {1}".format(self._name, self._path))
    elif updated:
      return self.ret(1, "User {0} modified".format(self._name))
    else:
      return self.ret(0, "No change on user {0}".format(self._name))

  def delete(self):
    '''Delete a given user
    '''

    code, path = self.__get_user_path()
    if code <= 0:
      return self.ret(code, path)

    data = {'deleteAuthorizable':  ''}
    code, result = self.curl(path, data)
    if code != 200:
      return self.ret(-1, "Error deleting user {0} - {1}".format(self._name, result))

    i = result.index('<div id="Message">OK</div>')
    if i > 0:
      return self.ret(1, "User {0} ({1}) deleted".format(path, self._name))
    else:
      return self.ret(-1, "Error on user delete")

  def password_change(self, oldpwd, newpwd):
    '''Sets new password for a user. Must provide old and new password.
    '''
    code, msg = self.__get_user_path()
    if code <= 0:
      return self.ret(code, msg)

    data = {'plain':  newpwd,
            'verify': newpwd,
            'old':    oldpwd,
            'Path':   self._path}

    code, result = self.curl('/crx/explorer/ui/setpassword.jsp', data)

    i = result.index('font color')
    j = result.index('>', i)
    k = result.index('</font', j)
    color = result[i+12:j-1]
    message = result[j+1:k]

    if color == 'red':
      return self.ret(-1, message)

    return self.ret(1, "Password changed for user {0}".format(self._name))

  def __set_groups(self, groups):
    ''' Add the user to given list of groups
    '''
    if len(groups) == 0:
      return (0, "No groups defined")

    for group in groups.split(","):
      code, groupPath = self.__get_group_path(group.strip())
      if code == 1:
        data = {'addMembers': self._name}

        url = "{0}.rw.html".format(groupPath)
        code, result = self.curl(url, data)
        if code != 200:
          return (-1, result)
      else:
        return (-1, "Unknown group {0}".format(group.strip()))

    return (1, "Groups modified")

  def __set_properties(self, properties):
    ''' Add properties to the user
    '''

    if self._path is None:
      return (-1, "User path not defined")

    if len(properties) == 0:
      return (0, "No properties defined")

    data = {}
    for key, value in properties.items():
      data.update({"profile/" + key: value})

    url = "{0}.rw.html".format(self._path)
    code, result = self.curl(url, data)
    if code != 200:
      return (-1, result)

    return (1, "Properties added")

# ===================================================================
def usage():
  print("Usage:")
  print("\tpython aemcli.py <args...>")
  print("")
  print("\t--package          = Run in package mode")
  print("\t--user             = Run in user mode")
  print("\t-i <...>           = IP address or hostname of the AEM instance. Default is localhost")
  print("\t-p <...>           = Port number of the AEM instance. Default is 4502")
  print("\t-a <...>           = 'admin' user password. Default is 'admin'")
  print("\t-n|--name <...>    = Name of package/user to install/create/update/delete... - Mandatory")
  print("\t-o|operation <...> = Operation to execute, depending of the selected mode - Mandatory")
  print("\t\tmode package : install / delete / uninstall / status")
  print("\t\tmode user    : create / delete / password / status")
  print("\t-s|--source <...>  = Source file for package installation - Mandatory if mode=package & operation=install")
  print("\t-f|--force         = Set force flag to True. Default is False")
  print("\t-u|--uninstall     = Set uninstall flag to True when deleting a package. Default is False")
  print("\t--replicate        = Set replicate flag to True when installing a package. Default is False")
  print("\t--oldpwd <...>     = Old password of the user when changing password")
  print("\t--newpwd <...>     = New password of the user when changing password or creating new user")
  print("\t--path <...>       = Folder name, under /home/users, where to create the user")
  print("\t--groups <...>     = Groups in which to add a new or updated user (comma separated string)")
  print("\t--srcusr <...>     = User for source authentication when HTTP(S) or FTP")
  print("\t--srcpwd <...>     = Password for source authentication when HTTP(S) or FTP")
  print("\t-P <...>           = Property to add / update on a user. Format: <key>=<value>. Use as many -P parameters than necessary")
  print("\t-h|--help          = Help")
  print("")
  print("Samples")
  print("- Status of a package:")
  print("    python aemcli.py --package -n <PACKAGE_NAME> --operation status")
  print("- Install a package:")
  print("    python aemcli.py --package -n <PACKAGE_NAME> --operation install -s <PACKAGE_FILE>")
  print("- Install a package and replicate on publish instances:")
  print("    python aemcli.py --package -n <PACKAGE_NAME> --operation install -s <PACKAGE_FILE> --replicate")
  print("- Uninstall and delete a package:")
  print("    python aemcli.py --package -n <PACKAGE_NAME> --operation delete --uninstall")
  print("- Delete a package without uninstalling:")
  print("    python aemcli.py --package -n <PACKAGE_NAME> --operation delete")
  print("")
  print("- Change password of a user:")
  print("    python aemcli.py --user -n <USER_ID> --operation password --oldpwd <OLD_PASSWORD> --newpwd <NEW_PASSWORD>")
  print("- Delete a user:")
  print("    python aemcli.py --user -n <USER_ID> --operation delete")

# ===================================================================
def main():
  try:
    opts, args = getopt.getopt(sys.argv[1:],
                               "hpa:un:o:s:fP:",
                               ["package", "user", "name=", "operation=", "force", "uninstall", "replicate",
                                "source=", "oldpwd=", "newpwd=", "path=", "groups=", "srcusr", "srcpwd", "help"])
  except getopt.GetoptError as err:
    print str(err)  # will print something like "option -a not recognized"
    usage()
    sys.exit(1)

  password = "admin"
  port = "4502"
  hostname = "localhost"

  mode = None
  name = None
  operation = None

  source = None
  srcusr = None
  srcpwd = None
  force = False
  uninstall = False
  replicate = False
  oldpwd = None
  newpwd = None
  path = None
  groups = None
  properties = {}

  for o, val in opts:
    if o == "-a":                     # admin user password
      password = val
    elif o == "-i":                   # AEM instance address (hostname or IP)
      hostname = val
    elif o == "-p":                   # AEM instance port number
      port = val
    elif o in ("-h", "--help"):       # Display help & exit
      usage()
      sys.exit()
    elif o == "--package":            # package commands mode
      mode = "package"
    elif o == "--user":               # user commands mode
      mode = "user"
    elif o in ("-n", "--name"):       # name of package or user
      name = val
    elif o in ("-o", "--operation"):  # operation ID
      operation = val
    elif o in ("-s", "--source"):     # Source file
      source = val
    elif o in ("-f", "--force"):      # Force flag
      force = True
    elif o in ("-u", "--uninstall"):  # Uninstall flag
      uninstall = True
    elif o == "--replicate":          # Replicate flag
      replicate = True
    elif o == "--oldpwd":             # User old password
      oldpwd = val
    elif o == "--newpwd":             # User new password
      newpwd = val
    elif o == "--path":               # Path for user creation
      path = val
    elif o == "--groups":             # Groups in which to add user
      srcusr = val
    elif o == "--srcusr":             # User for source authentication
      srcpwd = val
    elif o == "--srcpwd":             # Password for source authentication
      groups = val
    elif o == "-P":                   # User's property
      try:
        key, value = val.split('=')
      except ValueError:
        print >>sys.stderr, "Invalid user property {0}. Must be key=value".format(val)
        sys.exit(1)

      properties.update({key: value})
    else:
      assert False, "Unhandled option"

  if mode is None:
    print >>sys.stderr, "Running mode not defined. See help (-h|--help)"
    sys.exit(1)
  if name is None:
    print >>sys.stderr, "-n|--name argument is mandatory. See help (-h|--help)"
    sys.exit(1)
  if operation is None:
    print >>sys.stderr, "-o|--operation argument is mandatory. See help (-h|--help)"
    sys.exit(1)

  print("AEM admin tool")
  print("\thostname  = " + hostname)
  print("\tport      = " + port)
  print("\tmode      = " + mode)
  print("\tname      = " + name)
  print("\toperation = " + operation)

  result = None

  if mode == "package":
    aemCde = AEMPackage(name, port, password, hostname)

    if operation == "status":
      print("Checking status of {0} package ...".format(name))
      result = aemCde.status()
    elif operation == "install":
      print("Installing package {0} ...".format(name))
      result = aemCde.install(source, force, replicate, srcusr, srcpwd)
    elif operation == "delete":
      print("Deleting package {0} ...".format(name))
      result = aemCde.delete(uninstall)
    elif operation == "uninstall":
      print("Uninstalling package {0} ...".format(name))
      result = aemCde.delete(uninstall=True)
    else:
      print >>sys.stderr, "Operation {0} is not recognized for package mode. See help (-h|--help)".format(operation)
      sys.exit(1)

  elif mode == "user":
    aemCde = AEMUser(name, port, password, hostname)

    if operation == "create":
      print("Creating or updating user {0} ...".format(name))
      result = aemCde.create_or_update(newpwd, path, groups, properties)
    elif operation == "delete":
      print("Deleting user {0} ...".format(name))
      result = aemCde.delete()
    elif operation == "password":
      if oldpwd is None or newpwd is None:
        print >>sys.stderr, "Old and new password must be provided to change a user password"
        sys.exit(1)
      print("Changing password for user {0} ...".format(name))
      result = aemCde.password_change(oldpwd, newpwd)
    elif operation == "status":
      print "Not yet implemented"
    else:
      print >>sys.stderr, "Operation {0} is not recognized for user mode. See help (-h|--help)".format(operation)
      sys.exit(1)

  if result is not None:
    print(json.dumps(result, indent=4))

# ===================================================================
if __name__ == "__main__":
    main()