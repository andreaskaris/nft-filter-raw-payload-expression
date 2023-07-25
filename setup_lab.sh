#!/bin/bash

set -eux

sysctl -w net.ipv4.ip_forward=1

ip link add os-red type veth peer name red
ip link set dev os-red up
ip a a 192.168.123.1/24 dev os-red
ip netns add red
ip link set dev red netns red
ip netns exec red ip link set dev lo up
ip netns exec red ip a a dev red 192.168.123.11/24
ip netns exec red ip link set dev red up
ip netns exec red ip r a default via 192.168.123.1

ip link add os-blue type veth peer blue
ip link set dev os-blue up
ip a a 192.168.124.1/24 dev os-blue
ip netns add blue
ip link set dev blue netns blue
ip netns exec blue ip link set dev lo up
ip netns exec blue ip a a dev blue 192.168.124.11/24
ip netns exec blue ip link set dev blue up
ip netns exec blue ip r a default via 192.168.124.1
