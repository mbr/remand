VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ARTACK/debian-jessie"
  config.vm.box_url = "https://atlas.hashicorp.com/ARTACK/boxes/debian-jessie"
  config.vm.box_check_update = false
  #config.vm.synced_folder ".", "/vagrant", :mount_options => ['ro']
  config.vm.provision "shell",
    inline: "apt-get update && apt-get -y dist-upgrade && apt-get install -y python-virtualenv python-dev && sudo -u vagrant virtualenv /home/vagrant/remand-venv && cd /home/vagrant && sudo -u vagrant /home/vagrant/remand-venv/bin/pip install -e /vagrant && ln -s /home/vagrant/remand-venv/bin/remand /usr/local/bin"
end
