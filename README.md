PYTHONUNBUFFERED=1 ANSIBLE_FORCE_COLOR=true ANSIBLE_CONFIG='./ansible.cfg'  ansible-playbook --connection=ssh --timeout=30 --extra-vars=ansible_user\=\'root\' --limit="all" --inventory-file=./ansible/inventory/local/hosts-author.yml --extra-vars=\{\"aem_port\":4502,\"aem_mode\":\"author,prod\"\} -vvv ./ansible/install-author.yml


## PUBLISH
PYTHONUNBUFFERED=1 ANSIBLE_FORCE_COLOR=true ANSIBLE_CONFIG='./ansible.cfg'  ansible-playbook --connection=ssh --timeout=30 --extra-vars=ansible_user\=\'root\' --limit="all" --inventory-file=./ansible/inventory/local/hosts-publish.yml --extra-vars=\{\"aem_port\":4503,\"aem_mode\":\"publish,prod\"\} -vvv ./ansible/install-publish.yml



## aem-dev-env | Local Development Environment for AEM

This Vagrantfile and associated files will help you get set up quickly to run an AEM instance - AEM 6.x

 - [x] Author Instance
 - [x] Publish Instance
 - [ ] **ToDo** Dispatcher Configurations
 
 For provisioning the AEM instances, the script have been used from [ansible-aem-cms] by wcm.io
 
--------------------------------------------------------------------------------------------------------------------
### Pre-Requisite

This version of script assumes that all the installables and dependencies for the setup are placed under shared folder

 - Java `jdk-8u221-linux-x64.tar.gz`
 - AEM Jar `AEM_6.5_Quickstart.jar`
 - AEM Service Pack `AEM-6.5.6.0-6.5.6.zip`
 - AEM Core Component `core.wcm.components.all-2.9.0.zip`
 - AEM ACS Commons `acs-aem-commons-content-4.7.0.zip`
 - ACS Twitter Bundle `com.adobe.acs.bundles.twitter4j-content-1.0.0.zip`
 - AEM License File `icense.properties`

In case you want to use a different version of the packages/bundles, the names can be updated in `aem-dev-box/vagrant/ansible/inventory/local/group_vars/all`

--------------------------------------------------------------------------------------------------------------------

### Installation

For the setup, following software need to be installed -

 - [Vagrant]
 - [Virtual Box]
 - [Ansible] 

#### Install the Vagrant Omnibus plugin

    $ vagrant plugin install vagrant-omnibus
    
#### Install the Vagrant Hostsupdater plugin

    $ vagrant plugin install vagrant-hostsupdater
    
--------------------------------------------------------------------------------------------------------------------

### Usage

#### Starting the Instance

Scripts for the author instance have been placed under `aem-dev-box/vagrant/author` and for publish under `aem-dev-box/vagrant/publish`

 - cd into `vagrant/<author | publish>`
 - run `vagrant up`
 
 The will initiate the setup, when run for the first time, the scripts will provision the machine (install java and AEM). 
 In case of issues, you re-run the scripts by calling `vagrant up --provision`.
 
 AEM is installed under `/opt/adobe/aem`, When provisioning, the setup will take about 10 - 15 minutes or more depending upon network speed. 
 As multiple packages are installed into AEM, the startup time for the first run will be longer. You can ssh into the machine and tail the logs - 
 
 
    $ vagrant ssh
    $ tail -f /opt/adobe/aem/crx-quickstart/logs/error.log


#### Handy Vagrant Commands

 - `Vagrant up` - Starts the instance specified via Vagrantfile, when run for the first time, it also executes the provisioning scripts
 - `Vagrant halt` - Stops the instance
 - `Vagrant reload` - Restarts the instance
 - `Vagrant ssh` - SSH into the instance
 - `Vagrant destroy` - Destroys the instance
 
 --------------------------------------------------------------------------------------------------------------------
 
 ### Troubleshooting
 
 #### Network issues
 The first time you start a new Vagrant installation be careful around using VPNs at the same time - if you disconnect or connect to the VPN after starting up vagrant it can cause issues with networking.
 
 If you think this may have happened, disconnect from the VPN and do 
 
     $ vagrant destroy 
     $ vagrant up 
 
 This will restart the installation
 
 #### Updating software
 Make sure you have the latest versions of [Vagrant], [Virtual Box] and the plugins :
 
     $ rm -r ~/.vagrant.d/plugins.json ~/.vagrant.d/gems
     $ vagrant plugin install vagrant-berkshelf --plugin-version '>= 2.0.1'
     $ vagrant plugin install vagrant-omnibus

[Vagrant]: https://www.vagrantup.com/docs/installation
[Virtual Box]: https://www.virtualbox.org/wiki/Downloads
[Ansible]: https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html
[ansible-aem-cms]: https://github.com/wcm-io-devops/ansible-aem-cms