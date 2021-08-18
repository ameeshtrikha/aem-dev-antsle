require 'yaml'

ANSIBLE_TAGS=ENV['ANSIBLE_TAGS']
ENV['ANSIBLE_ROLES_PATH'] = "../../ansible/roles"


# Method to Load default config from config_local.yaml. If config_local.yaml exists then merge into default config.
def deep_merge!(src, override)
  override.each do |key, oval|
    # puts "merging #{key}"
    if src.has_key?(key)
      sval = src[key]
      if oval == sval
        # puts "Values are identical"
        next
      elsif oval.is_a?(Hash) and sval.is_a?(Hash)
        # puts "Deep merging subhashes"
        deep_merge!(sval, oval)
      elsif oval.is_a?(Array) and sval.is_a?(Array)
        # puts "Deep merging arrays"
        sval.concat oval
      else
        # puts "Overriding value #{sval.inspect} with #{oval.inspect}"
        src[key] = oval
      end
    else
      # puts "adding new value {#{key} => #{oval}}"
      src[key] = oval
    end
  end
  return src
end

module VagrantConfig
  # Method to check if a local port it open
  def is_local_port_open?(port)
    begin
      Timeout::timeout(2) do
        begin
          s = TCPSocket.new('127.0.0.1', port)
          s.close
          return true
        rescue Errno::ECONNREFUSED, Errno::EHOSTUNREACH
        end
      end
    rescue Timeout::Error
    end
    return false
  end

  # Method to configure the box name and url (if exists)
  def configure_box(config, box_name, box_url, box_version)
    # Every Vagrant virtual environment requires a box to build off of.
    config.vm.box = box_name
    config.vm.box_version = box_version

    if box_url
      # The url from where the 'config.vm.box' box will be fetched if it
      # doesn't already exist on the user's system.
      config.vm.box_url = box_url
    end
  end

  # Method to configure port forwards
  def configure_port_forwarding(config, port_forwards)
    port_forwards.each do |name, forward|
      if is_local_port_open? forward['host_port']
        puts "[WARN] Port #{forward['host_port']} is in use."
      end
      config.vm.network :forwarded_port, guest: forward['guest_port'], host: forward['host_port']
    end
  end

  # Method to configure share folders
  def configure_shared_folders(config, shared_folders)
    shared_folders.each do |name, folder|
      config.vm.synced_folder folder['host_path'], folder['vm_path'], mount_options: ['dmode=777,fmode=777'], create: true
    end
  end

  # Method to configure the provider
  def configure_provider(config, vm_name, cpus, memory_size, box_os)
    config.vm.provider :virtualbox do |vb|
      # Configure VM resources
      vb.gui = false
      vb.name = vm_name
      vb.cpus = cpus
      vb.memory = memory_size

      # allow symlinks to creation in default vagrant share folder https://github.com/mitchellh/vagrant/issues/713
      vb.customize ["setextradata", :id, "VBoxInternal2/SharedFoldersEnableSymlinksCreate/v-root", "1"]
      if box_os == "ubuntu"
        # Fix for network name lookups broken in NAT network adapters
        # see https://bugs.launchpad.net/ubuntu/+source/virtualbox/+bug/1048783
        vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
      end
    end
  end

  # Method to configure private network IP
  def configure_private_network_ip(config, ip, vm_name)
    if ip
      config.vm.network :private_network, :ip => ip, :netmask => "255.255.255.0"
    else
      puts " NO HOSTONLY IP defined for VM #{vm_name}."
    end
  end

  # Method to configure host name
  def configure_host_name(config, host_name)
    if host_name
      config.hostsupdater.remove_on_suspend = true
      config.vm.host_name = host_name
      config.hostsupdater.aliases = ["secure.#{host_name}"]
    end
  end

  def configure_ansible_provision(config, allVars)
    config.vm.provision "install", type: "ansible" do |ansible|
          ansible.playbook       = "../ansible/install-"+allVars['aem_mode']+".yml"
          ansible.inventory_path = "../ansible/inventory/local/hosts-"+allVars['aem_mode']+".yml"
          ansible.config_file = "../ansible.cfg"
          # Disable default limit to connect to all the machines
          ansible.limit   = "all"
          ansible.verbose = "vvv"
          ansible.tags    = ANSIBLE_TAGS
          ansible.extra_vars = {
          aem_port: allVars['aem_port'],
          aem_mode: allVars['aem_mode']
          }
    end
  end

  def vagrant_setup(box_name)
    # Load default config from config_local.yaml. If config_local.yaml exists then merge into default config.
    # By default keep all VMs disabled in config_local.yaml and enable specific VMs in config_local.yaml.
    conf = YAML::load_file(File.expand_path('../config.yaml'))
    conf_local = YAML::load_file(File.expand_path('config_local.yaml')) rescue {}
    begin
      deep_merge!(conf, conf_local)
    end

    Vagrant.configure(2) do |global_config|

      config = conf['vms']['vbox']

      # Configure the Box Name and URL (if exists)
      configure_box(global_config, config['box_name'], config['box_url'], config['box_version'])

      # Boot with a GUI so you can see the screen. (Default is headless)
      global_config.vm.boot_mode = :gui if config['gui']

      # Configure Port Forwarding
      configure_port_forwarding(global_config, config['port_forwards'])

      # Configure Shared Folders
      configure_shared_folders(global_config, config['shared_folders'])

      # VirtualBox Specific Configuration
      configure_provider(global_config, config['instance_name'], config['cpus'], config['memory_size'], config['box_os'])

      # Setup Private Network IP & Bridge
      configure_private_network_ip(global_config, config['ip'], config['instance_name'])

      # Setup Guest HostName
      configure_host_name(global_config, config['host_name'])

      # Configure chef_solo
      configure_ansible_provision(global_config, config)
    end
  end
end
