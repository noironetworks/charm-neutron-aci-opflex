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

     Options are 'vlan' or 'vxlan'. 

     (vlan)

aci-apic-system-id:

     (string)

     A id string for this openstack instance

     (openstack)

aci-infra-vlan

     (int)

     ACI Fabric Infra vlan. (This cannot be changed once the charm is deployed)
 
     4093

aci-opflex-peer-ip

     (string)

     Opflex Peer ip on ACI. Consult ACI fabric installation

     10.0.0.30

aci-opflex-remote-ip

     (string)

     Opflex peer remote ip on ACI. Consult ACI fabric installation

     10.0.0.32

aci-uplink-interface

     (string)

     Uplink interface from server to ACI fabric. eg eth2 or bond0


Author: Ratnakar Kolli (rkolli@noironetworks.com)
Report bugs at: 
Location: 


