#!/usr/bin/env python3

from collections import OrderedDict
from copy import deepcopy
import socket
import subprocess
import sys
from itertools import chain

ACI_OPFLEX_PACKAGES = [
   'openvswitch-switch', 
   'agent-ovs', 
   'neutron-opflex-agent',
   'neutron-metadata-agent',
]

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    log,
    relation_set,
    relation_get,
    relation_ids,
    status_set,
    is_relation_made,
    is_leader,
    INFO,
)

from charmhelpers.contrib.network.ovs import (
    add_bridge,
    add_bridge_port,
    full_restart,
)

from charmhelpers.core.host import (
    restart_on_change,
    service_restart
)

from charmhelpers.contrib.openstack import context, templating
import aci_opflex_context

from charmhelpers.contrib.openstack.utils import (
    pause_unit,
    resume_unit,
    make_assess_status_func,
    is_unit_paused_set,
    os_release,
)

from charmhelpers.core.host import (
    adduser,
    add_group,
    add_user_to_group,
    lsb_release,
    mkdir,
    service,
    service_restart,
    service_running,
    write_file,
)

from charmhelpers import fetch

OPFLEX_CONFIG = "/etc/opflex-agent-ovs/conf.d/opflex-agent-ovs.conf"
OPFLEX_SERVICES = ['agent-ovs', 'neutron-opflex-agent']
NEUTRON_CONF_DIR = "/etc/neutron"
NEUTRON_CONF = '%s/neutron.conf' % NEUTRON_CONF_DIR
OVS_CONF = '%s/plugins/ml2/openvswitch_agent.ini' % NEUTRON_CONF_DIR
NEUTRON_METADATA_AGENT_CONF = "/etc/neutron/metadata_agent.ini"
TEMPLATES = 'templates/'

BASE_RESOURCE_MAP = OrderedDict([
    (OPFLEX_CONFIG, {
        'services': OPFLEX_SERVICES,
        'contexts': [aci_opflex_context.AciOpflexConfigContext(),],
    }),
    (NEUTRON_CONF, {
        'services': OPFLEX_SERVICES,
        'contexts': [aci_opflex_context.RemoteRestartContext(
                         ['neutron-plugin', 'neutron-control']),
                     context.AMQPContext(ssl_dir=NEUTRON_CONF_DIR)],
    }),
    (OVS_CONF, {
        'services': OPFLEX_SERVICES,
        'contexts': [aci_opflex_context.OVSPluginContext()],
    }),
    (NEUTRON_METADATA_AGENT_CONF, {
        'services': OPFLEX_SERVICES,
        'contexts': [aci_opflex_context.AciNeutronMetadataConfigContext(),],
    }),
])

REQUIRED_INTERFACES = {
   'messaging': ['amqp'],
}

UNSUPPORTED_CONFIG_CHANGES = [
        'aci-infra-vlan',
        'aci-uplink-interface'
]

INT_BRIDGE = "br-fabric"
EXT_BRIDGE = "br-ex"
DATA_BRIDGE = 'br-data'

def register_configs(release=None):
    release = release or os_release('neutron-common')
    configs = templating.OSConfigRenderer(templates_dir=TEMPLATES,
                                          openstack_release=release)
    for cfg, rscs in resource_map().items():
        configs.register(cfg, rscs['contexts'])
    return configs

def resource_map(release=None):
    '''
    Dynamically generate a map of resources that will be managed for a single
    hook execution.
    '''
    resource_map = deepcopy(BASE_RESOURCE_MAP)

    return resource_map

def restart_map():
    '''
    Constructs a restart map based on charm config settings and relation
    state.
    '''
    return {k: v['services'] for k, v in resource_map().items()}

def services():
    """Returns a list of (unique) services associate with this charm
    @returns [strings] - list of service names suitable for (re)start_service()
    """
    s_set = set(chain(*restart_map().values()))
    return list(s_set)


CONFIGS = register_configs()

def aci_opflex_install_pkgs():
    opt = ['--option=Dpkg::Options::=--force-confdef' ,'--option=Dpkg::Options::=--force-confold']

    conf = config()

    if 'aci-repo-key' in conf.keys():
        fetch.add_source(conf['aci-repo'], key=conf['aci-repo-key'])
    else:
        fetch.add_source(conf['aci-repo'])
        opt.append('--allow-unauthenticated')

    fetch.apt_update(fatal=True)
    fetch.apt_upgrade(fatal=True)

    fetch.apt_install(['neutron-common', 'neutron-server'], options=opt, fatal=True)
    fetch.apt_install(ACI_OPFLEX_PACKAGES, options=opt, fatal=True)

    cmd = ['/bin/systemctl', 'stop', 'neutron-metadata-agent']
    subprocess.check_call(cmd)

    cmd = ['/bin/systemctl', 'disable', 'neutron-metadata-agent']
    subprocess.check_call(cmd)

    cmd = ['touch', '/etc/neutron/plugin.ini']
    subprocess.check_call(cmd)

def create_opflex_interface():
    conf = config()
    status_set('maintenance', 'Configuring Opflex Interface')

    infra_vlan = conf['aci-infra-vlan']
    #infra_vlan = 3901
    data_port = conf['aci-uplink-interface']
    with open("/sys/class/net/%s/address" % data_port, 'r') as iffile:
        data_port_mac = iffile.read()

    with open('/etc/network/interfaces.d/opflex.cfg', 'w') as iffile:
        content = """
auto %s.%s
iface %s.%s inet dhcp
vlan-raw-device %s
post-up /sbin/route -nv add -net 224.0.0.0/4 dev %s.%s
""" % (data_port, infra_vlan, data_port, infra_vlan, data_port, data_port, infra_vlan)
        iffile.write(content)

    with open('/etc/dhcp/dhclient.conf', 'w') as iffile:
        content = """
interface "%s.%s" {
   send host-name %s;
   send dhcp-client-identifier 01:%s;
}
         """ % (data_port, infra_vlan, socket.gethostname(), data_port_mac.strip())
        iffile.write(content)

    cmd = ['/sbin/ifup', '%s.%s' % (data_port, infra_vlan)]
    subprocess.check_call(cmd)

    if conf['aci-encap'] == 'vxlan':
        cmd = ['/usr/bin/ovs-vsctl', 'list-ports', 'br-fabric']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        brlist = p.stdout.read().decode().split('\n')

        if not 'br-fab_vxlan0' in brlist:
            cmd = ['/usr/bin/ovs-vsctl', 'add-port', 'br-fabric', 'br-fab_vxlan0', '--',
                   'set', 'Interface', 'br-fab_vxlan0', 'type=vxlan',
                   'options:remote_ip=flow', 'options:key=flow', 'options:dst_port=8472']
            subprocess.check_call(cmd)

def configure_ovs():
    status_set('maintenance', 'Configuring ovs')
    if not service_running('openvswitch-switch'):
        full_restart()
    datapath_type = 'system'
    add_bridge(INT_BRIDGE, datapath_type)
    #add_bridge(EXT_BRIDGE, datapath_type)
    add_bridge_port(INT_BRIDGE, config('aci-uplink-interface'), promisc=True)

def configure_opflex():
    conf = config()
    for key in UNSUPPORTED_CONFIG_CHANGES:
        if conf.changed(key):
            log("Config change for %s not supported" % key, INFO)
            return
    configure_ovs()
    create_opflex_interface()

def assess_status(configs):
    """Assess status of current unit
    Decides what the state of the unit should be based on the current
    configuration.
    SIDE EFFECT: calls set_os_workload_status(...) which sets the workload
    status of the unit.
    Also calls status_set(...) directly if paused state isn't complete.
    @param configs: a templating.OSConfigRenderer() object
    @returns None - this function is executed for its side-effect
    """
    assess_status_func(configs)()


def assess_status_func(configs):
    """Helper function to create the function that will assess_status() for
    the unit.
    Uses charmhelpers.contrib.openstack.utils.make_assess_status_func() to
    create the appropriate status function and then returns it.
    Used directly by assess_status() and also for pausing and resuming
    the unit.
    Note that required_interfaces is augmented with neutron-plugin-api if the
    nova_metadata is enabled.
    NOTE(ajkavanagh) ports are not checked due to race hazards with services
    that don't behave sychronously w.r.t their service scripts.  e.g.
    apache2.
    @param configs: a templating.OSConfigRenderer() object
    @return f() -> None : a function that assesses the unit's workload status
    """
    required_interfaces = REQUIRED_INTERFACES.copy()
    return make_assess_status_func(
        configs, required_interfaces,
        services=services(), ports=None)


def pause_unit_helper(configs):
    """Helper function to pause a unit, and then call assess_status(...) in
    effect, so that the status is correctly updated.
    Uses charmhelpers.contrib.openstack.utils.pause_unit() to do the work.
    @param configs: a templating.OSConfigRenderer() object
    @returns None - this function is executed for its side-effect
    """
    _pause_resume_helper(pause_unit, configs)


def resume_unit_helper(configs):
    """Helper function to resume a unit, and then call assess_status(...) in
    effect, so that the status is correctly updated.
    Uses charmhelpers.contrib.openstack.utils.resume_unit() to do the work.
    @param configs: a templating.OSConfigRenderer() object
    @returns None - this function is executed for its side-effect
    """
    _pause_resume_helper(resume_unit, configs)


def _pause_resume_helper(f, configs):
    """Helper function that uses the make_assess_status_func(...) from
    charmhelpers.contrib.openstack.utils to create an assess_status(...)
    function that can be used with the pause/resume of the unit
    @param f: the function to be used with the assess_status(...) function
    @returns None - this function is executed for its side-effect
    """
    # TODO(ajkavanagh) - ports= has been left off because of the race hazard
    # that exists due to service_start()
    f(assess_status_func(configs),
      services=services(),
      ports=None)
