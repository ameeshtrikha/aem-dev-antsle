#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# AEM packages management module for Ansible


from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.aemcli import AEMPackage

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview']}

DOCUMENTATION = r'''
---
module: aem_package
short_description: Manages packages in an AEM instance
options:
  port:
    description:
      - Port of local AEM instance to connect to
    default: '4502'
  admin_pwd:
    description:
      - Password of the AEM admin user
    default: admin
  name:
    description:
      - Name of the package
    required: true
  src:
    description:
      - Source of the package (ZIP file) to upload in AEM. Required only if state=present
  srcusr:
    description:
      - User for source authentication when HTTP(S) or FTP. Required only if state=present
  srcpwd:
    description:
      - Password for source authentication when HTTP(S) or FTP. Required only if state=present
  state:
    description:
      - State of the user account: 'present' (default) to create or update, absent to 'delete'
    default: present
  installed:
    description:
      When state=absent, if True, the package is deleted but the content stay in the repository, else the
      package is uninstalled before being deleted.
    default: True
  force:
    description:
      - Used when state=present. Will force reinstallation of a package even if already installed.
    default: False
  replicate:
    description:
      - Used when state=present. Will replicate installation of a package on publish instances (author only).
    default: False
'''

# =========================================
def check_package(module, aemCde):
  return aemCde.status()

# =========================================
def delete_package(module, aemCde):
  result = aemCde.delete(uninstall = not module.params['installed'])
  code = result['code']
  msg  = result['msg']
  if code < 0:
    module.fail_json(msg=msg)
  elif code == 0:
    return False, msg
  else:
    return True, msg

# =========================================
def install_package(module, aemCde):
  result = aemCde.install(src = module.params['src'], force = module.params['force'],
                          replicate = module.params['replicate'], srcusr = module.params['srcusr'],
                          srcpwd = module.params['srcpwd'])
  code = result['code']
  msg  = result['msg']
  if code < 0:                  # Error
    module.fail_json(msg=msg)
  elif code == 0:
    return False, msg           # No change, already installed
  else:
    return True, msg            # Installed

# =========================================
# Module entry point.
#
def main():

  module = AnsibleModule(argument_spec = dict(
      port      = dict(type='str', default='4502'),
      admin_pwd = dict(type='str', default='admin', no_log=True),
      name      = dict(type='str', required=True),
      src       = dict(type='str'),
      srcusr    = dict(type='str'),
      srcpwd    = dict(type='str', no_log=True),
      state     = dict(type='str', default='present', choices=['present', 'absent']),
      installed = dict(type='bool', default=True),
      force     = dict(type='bool', default=False),
      replicate = dict(type='bool', default=False)
    )
  )

  aemCde = AEMPackage(module.params['name'], module.params['port'], module.params['admin_pwd'])
  if module.params['state'] == 'present':
    has_changed, result = install_package(module, aemCde)
  else:
    has_changed, result = delete_package(module, aemCde)

  module.exit_json(changed=has_changed, meta=result)

if __name__ == '__main__':
  main()