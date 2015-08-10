"""
This script creates and configures a linux network namespace such that an
application can be executed under the context of a virtualized network.
"""

import argparse
import socket
import sys

from instance_provisioner import Provisioner
from lxc_manager import LxcManager
from vrouter_control import interface_register


def build_network_name(project_name, network_name):
    if network_name.find(':') >= 0:
        return network_name
    return "%s:%s" % (project_name, network_name)


def daemon_start():
    """
    Creates a virtual-machine and vmi object in the API server.
    Creates a namespace and a veth interface pair.
    Associates the veth interface in the master instance with the vrouter.
    """
    parser = argparse.ArgumentParser()
    defaults = {
        'api-server': '127.0.0.1',
        'api-port': 8082,
        'project': 'default-domain:default-project',
        'network': 'default-network',
    }
    parser.set_defaults(**defaults)
    parser.add_argument("-s", "--api-server", help="API server address")
    parser.add_argument("-p", "--api-port", type=int, help="API server port")
    parser.add_argument("--project", help="OpenStack project name")
    parser.add_argument("-n", "--network", help="Primary network")
    parser.add_argument("-o", "--outbound", help="Outbound traffic network")
    parser.add_argument("daemon", help="Deamon Name")

    arguments = parser.parse_args(sys.argv[1:])

    manager = LxcManager()
    provisioner = Provisioner(api_server=arguments.api_server,
                              api_port=arguments.api_port)
    vrouter_name = socket.gethostname()
    instance_name = '%s-%s' % (vrouter_name, arguments.daemon)
    project_fq_name = arguments.project.split(':')
    project = provisioner.project_lookup(project_fq_name)
    vm = provisioner.virtual_machine_locate(vrouter_name, instance_name, project)

    network = build_network_name(arguments.project, arguments.network)

    vmi = provisioner.vmi_locate(vm, network, 'veth0', project)
    vmi_out = None
    if arguments.outbound:
        outbound_name = build_network_name(arguments.project,
                                           arguments.outbound)
        vmi_out = provisioner.vmi_locate(vm, outbound_name, 'veth1')

    manager.namespace_init(arguments.daemon)
    ifname = manager.interface_update(arguments.daemon, vmi, 'veth0')
    interface_register(vm, vmi, ifname, project=project)

    if vmi_out:
        ifname = manager.interface_update(arguments.daemon, vmi_out, 'veth1')
        interface_register(vm, vmi_out, ifname)

    single_interface = (arguments.outbound is None)
    ip_prefix = provisioner.get_interface_ip_prefix(vmi)
    manager.interface_config(arguments.daemon, 'veth0',
                             advertise_default=single_interface,
                             ip_prefix=ip_prefix)
    if vmi_out:
        manager.interface_config(arguments.daemon, 'veth1')

# end daemon_start


if __name__ == '__main__':
    daemon_start()
