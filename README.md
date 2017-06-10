Overview
--------

This charm is a subordinate to nova-compute charm and provides Opflex connectivity to ACI fabric.


Usage
-----

juju deploy --repository=<path> local:xenial/neutron-aci-opflex --config=<config> neutron-aci-opflex
juju add-relation neutron-aci-opflex:neutron-plugin-api neutron-api:neutron-plugin-api
juju add-relation neutron-aci-opflex:neutron-plugin nova-compute:neutron-plugin
juju add-relation neutron-aci-opflex:amqp rabbitmq-server:amqp
juju add-relation neutron-aci-opflex:quantum-network-service neutron-gateway:quantum-network-service


Configuration
-------------
aci-repo

     (string)

     Repository url for ACI plugin packages

aci-repo-key

     (string)

     GPG key for aci-repo. If not specified, packages will be installed with out authentication

aci-encap

     (string)

     Options are 'vlan' or 'vxlan'. When 'use-opflex' is set to False, this value is ignored and encap is forced to vlan.

     (vlan)

apic-hosts

     (string)

     Comma separated list of ACI controller host names or ip addresses

apic-username

     (string)

     username for ACI controller
 
     admin

apic-password

     (string)

     password for ACI user

use-vmm

     (string)

     If true, api creates a openstack vmm domain, if false it uses domain specified by apic-domain-name

     True

apic-domain-name

     (string)

     Name of aci domain for this openstack instance

apic-connection-json

     (string)

     Describes nova-compute connections to ACI leaf in JSON format. Example {'101': ['host1.domain:1/1', 'host2.domain:1/2'], '102':['host3.domain:1/4']}. 101 is the switch id, host1.domain is connected to port 1/1 

apic-vpc-pairs

     (string)
     
     If using VPC to connect the nodes to ACI leaf switches, specify the switch id pairs for vpc. Example, if switch ids 101 and 102 form a vpc pair and switch ids 103, 104 form a vpc pair, then set the value to '101:102,103:104'



Author: Ratnakar Kolli (rkolli@noironetworks.com)
Report bugs at: 
Location: 


