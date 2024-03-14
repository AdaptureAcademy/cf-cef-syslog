# -*- mode: ruby -*-
# vi: set ft=ruby :
 
VAGRANTFILE_API_VERSION = "2"
 
Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  # Define the syslog client
  config.vm.define "syslog_client" do |client|
    client.vm.box = "generic/centos7"
    client.vm.network "private_network", ip: "192.168.56.10"
    client.vm.hostname = "syslog-client"
    client.vm.provision "shell", inline: <<-SHELL
      yum install -y python3 python3-pip
      pip3 install --upgrade pip
      # Add additional Python packages installation commands here
    SHELL
  end
 
  # Define the syslog server
  config.vm.define "syslog_server" do |server|
    server.vm.box = "generic/centos7"
    server.vm.network "private_network", ip: "192.168.56.20"
    server.vm.hostname = "syslog-server"
    server.vm.provision "shell", inline: <<-SHELL
      yum install -y rsyslog
      # Configure rsyslog to listen on UDP port 514
      sed -i 's/#\$ModLoad imudp/\$ModLoad imudp/' /etc/rsyslog.conf
      sed -i 's/#\$UDPServerRun 514/\$UDPServerRun 514/' /etc/rsyslog.conf
      systemctl start rsyslog
      systemctl enable rsyslog
      firewall-cmd --permanent --add-port=514/udp && firewall-cmd --reload
    SHELL
  end
end