#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# AEM users accounts management module for Ansible


from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url
import json, urllib
from ansible.module_utils.aemcli import AEMUser

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview']}

DOCUMENTATION = r'''
---
module: aem_user
short_description: Creates, updates or deletes AEM users
options:
  port:
    description:
      - Port of local AEM instance to connect to
    default: '4502'
  admin_pwd:
    description:
      - Password of the AEM admin user
    default: 'admin'
  user:
    description:
      - User name
    required: true
  password:
    description:
      - Password of the user to create, or current password when changing password
  new_password:
    description:
      - New password when changing password
  path:
    description:
      - Folder name, under /home/users, to create the user
  groups:
    description:
      - Groups the user should be added 
  state:
    description:
      - State of the user account: 'present' (default) to create or update, absent to 'delete', 'password' to change password
        Note: Password can not be updated with state = 'present'
    default = present
  fail_on_error:
    description:
      - If True (default), execution will fail if an error occur.
    default: True
'''

# =========================================
def get_group_path(module, group):
  '''Returns the path to a given group in the AEM repository.
     If the group doesn't exist, returns None
  '''

  url = ("http://localhost:%s/bin/querybuilder.json?"
         "path=/home/groups&1_property=rep:authorizableId&"
         "1_property.value=%s&p.limit=-1"
         % (module.params['port'], group))

  resp, info = fetch_url(module, url, method="GET")
  test_http_fail(module, info)

  body = json.loads(resp.read())
  success = body["success"]
  results = body["results"]
  if not success or results != 1:
    return None
  else:
    return body["hits"][0]["path"]

# =========================================
def get_user_path(module):
  '''Returns the path to a given user in the AEM repository.
     If the user doesn't exist, returns None
  '''

  url = ("http://localhost:%s/bin/querybuilder.json?"
         "path=/home/users&1_property=rep:authorizableId&"
         "1_property.value=%s&p.limit=-1"
         % (module.params['port'], module.params['user']))

  resp, info = fetch_url(module, url, method="GET")
  test_http_fail(module, info)

  body = json.loads(resp.read())
  success = body["success"]
  results = body["results"]
  if not success or results != 1:
    return None
  else:
    return body["hits"][0]["path"]

# =========================================
def create_or_update(module):
  '''Creates or updates user.
  '''

  path = get_user_path(module)
  if path is None:
    return create_user(module)

  has_changed = False
  return (has_changed, path)

# =========================================
def create_user(module):
  '''Creates a new user.
  '''

  data = {'createUser': module.params['user'],
          'authorizableId': module.params['user'],
          'rep:password': module.params['password']}

  if module.params['path'] is not None:
    data.update({'intermediatePath': module.params['path']})

  encodedData = urllib.urlencode(data)
  url = ("http://localhost:%s/libs/granite/security/post/authorizables" % (module.params['port']))
  resp, info = fetch_url(module, url, data = encodedData, method = 'POST')
  test_http_fail(module, info)

  body = resp.read()
  i = body.index('<div id="Message">Created</div>')
  if i > 0:
    i = body.index('<div id="Path">', i)
    j = body.index('</div>', i)
    path = body[i+15:j]

    # Add user to groups
    if module.params['groups'] is not None:
      for group in module.params['groups'].split(","):
        groupPath = get_group_path(module, group.strip())
        if groupPath is not None:
          data = {'addMembers': module.params['user']}
          encodedData = urllib.urlencode(data)

          url = ("http://localhost:%s%s.rw.html" % (module.params['port'], groupPath))
          resp, info = fetch_url(module, url, data = encodedData, method = 'POST')
          test_http_fail(module, info)
        else:
          module.fail_json(msg="Unknown group %s" % group.strip())

    return (True, "User %s created in path %s" % (module.params['user'], path))
  else:
    module.fail_json(msg="Error on user creation")

# =========================================
def delete_user(module):
  '''Deletes a user.
  '''

  path = get_user_path(module)
  if path is None:
    return (False, "User not found")

  data = {'deleteAuthorizable':  ''}
  encodedData = urllib.urlencode(data)

  url = ("http://localhost:%s%s" % (module.params['port'], path))
  resp, info = fetch_url(module, url, data = encodedData, method = 'POST')
  test_http_fail(module, info)

  body = resp.read()
  i = body.index('<div id="Message">OK</div>')
  if i > 0:
    return (True, "User %s (%s) deleted" % (path, module.params['user']))
  else:
    module.fail_json(msg="Error on user delete")

# =========================================
def set_password(module):
  '''Sets new password for a user. Must provide old and new password.
  '''

  path = get_user_path(module)
  if path is None:
    if module.params['fail_on_error']:
      module.fail_json(msg="User not found")
    else:
      return (False, "User not found")

  data = {'plain':  module.params['new_password'],
          'verify': module.params['new_password'],
          'old':    module.params['password'],
          'Path':   path}
  encodedData = urllib.urlencode(data)

  url = ("http://localhost:%s/crx/explorer/ui/setpassword.jsp" % (module.params['port']))
  resp, info = fetch_url(module, url, data = encodedData, method = 'POST')
  test_http_fail(module, info)

  body = resp.read()
  i = body.index('font color')
  j = body.index('>', i)
  k = body.index('</font', j)
  color = body[i+12:j-1]
  message = body[j+1:k]

  if color == 'red':
    if module.params['fail_on_error']:
      module.fail_json(msg=message)
    else:
      return (False, message)

  return (True, message)

# =========================================
def test_http_fail(module, info):
  '''Fail module on HTTP error.
  '''
  if info["status"] >= 400:
    module.fail_json(msg="HTTP error %s - %s" % (str(info["status"]), info["msg"]))

# =========================================
# Module entry point.
#
def main():

  module = AnsibleModule(argument_spec = dict(
      port          = dict(type='str', default='4502'),
      admin_pwd     = dict(type='str', default='admin', no_log=True),
      user          = dict(type='str', required=True),
      password      = dict(type='str', no_log=True),
      new_password  = dict(type='str', no_log=True),
      path          = dict(type='str'),
      groups        = dict(type='str'),
      state         = dict(type='str', default='present', choices=['present', 'absent']),
      fail_on_error = dict(type='bool', default=True)
    )
  )

  # Authentication configuration for fetch_url
  module.params['url_username'] = 'admin'
  module.params['url_password'] = module.params['admin_pwd']
  module.params['force_basic_auth'] = True
  module.params.pop('admin_pwd', None)

  aemCde = AEMUser(module.params['name'], module.params['port'], module.params['admin_pwd'])
  if module.params['state'] == 'present':
    if module.params['password'] is None:
      module.fail_json(msg="Password required when creating or updating a user")
    if module.params['new_password'] is None:
      has_changed, result = create_or_update(module)
    else:
      has_changed, result = set_password(module)
  else:
    has_changed, result = delete_user(module)

  module.exit_json(changed=has_changed, meta=result)

if __name__ == '__main__':
  main()