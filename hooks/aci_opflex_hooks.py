#!/usr/bin/env python

from collections import OrderedDict
from copy import deepcopy
import subprocess
import sys
import pdb

from aci_opflex_utils import (
    ACI_OPFLEX_PACKAGES,
    aci_opflex_install_pkgs,
    configure_opflex,
    assess_status,
    register_configs,
    restart_map,
)

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    log,
    relation_set,
    relation_get,
    relation_ids,
    is_relation_made,
    is_leader,
    unit_get,
    network_get_primary_address,
)

from charmhelpers.core.host import (
    restart_on_change,
    service_restart
)

from charmhelpers.contrib.openstack import context, templating
import aci_opflex_context

from charmhelpers.contrib.openstack.utils import (
    os_release,
)

from charmhelpers import fetch

hooks = Hooks()
CONFIGS = register_configs()

@hooks.hook()
@hooks.hook('install')
def aci_opflex_install(relation_id=None):
    log("Installing ACI Opflex packages")

    aci_opflex_install_pkgs()

@hooks.hook('update-status')
def update_status():
    log("Updating status")

@hooks.hook('neutron-plugin-relation-changed')
@restart_on_change(restart_map=restart_map(), stopstart=True)
@hooks.hook('config-changed')
def config_changed():
    aci_opflex_install()
    configure_opflex()
    CONFIGS.write_all()
    for rid in relation_ids('neutron-plugin'):
        neutron_plugin_joined(relation_id=rid)

@hooks.hook('neutron-plugin-api-relation-changed')
@restart_on_change(restart_map=restart_map(), stopstart=True)
def neutron_plugin_api_changed():
    CONFIGS.write_all()
    # If dvr setting has changed, need to pass that on
    for rid in relation_ids('neutron-plugin'):
        neutron_plugin_joined(relation_id=rid)

@hooks.hook('amqp-relation-joined')
def amqp_joined(relation_id=None):
    relation_set(relation_id=relation_id,
                 username=config('rabbit-user'),
                 vhost=config('rabbit-vhost'))

@hooks.hook('neutron-plugin-relation-joined')
def neutron_plugin_joined(relation_id=None):
    rel_data = {}
    relation_set(relation_id=relation_id, **rel_data)

@hooks.hook('amqp-relation-changed')
@hooks.hook('amqp-relation-departed')
@restart_on_change(restart_map=restart_map(), stopstart=True)
def amqp_changed():
    if 'amqp' not in CONFIGS.complete_contexts():
        log('amqp relation incomplete. Peer not ready?')
        return
    CONFIGS.write_all()

@hooks.hook('quantum-network-service-relation-joined')
@hooks.hook('quantum-network-service-relation-changed')
def qns_changed():
    if 'quantum-network-service' not in CONFIGS.complete_contexts():
        log('quantum-network-service relation incomplete. Peer not ready?')
        return
    CONFIGS.write_all()

#@hooks.hook('upgrade-charm')    
#def upgrade_charm():
#    aci_install()
#    config_changed()
#

def main():
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))
    assess_status(CONFIGS)

if __name__ == '__main__':
    main()
