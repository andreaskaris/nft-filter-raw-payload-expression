# Using nftables with raw payload expressions

The following is a walkthrough of how to use nft raw payload expressions to apply nftables filters with custom L4
protocol payload. We are going to define a very simply custom protocol on top of UDP alongside a python client and
server implementation. Then, we are going to send messages between client and server. As a final step, we are going
to use nftables' raw payload expressions to filter packets based on the contents of the fields of our custom protocol.

## Custom message protocol

[client_server.py](client_server.py) implements a simple message protocol on top of UDP. The message protocol has
2 fields, `message code` and `message op`. Each of the fields is 2 bytes long.

```
+--------------+--------------+
| message code |  message op  |
+--------------+--------------+
    2 bytes        2 bytes
```

Message codes:
```                                                                             
MESSAGE_CODE_VALID = 1                                                          
MESSAGE_CODE_INVALID = 1337
```

Message ops:
```
MESSAGE_OP_SEND = 0                                                             
MESSAGE_OP_REPLY = 1
```

When the clients sends a valid message, it will send `(1,0)`, for `(valid, send)`. The server will then mirror the
message code, change the message op to `reply` and return `(1,1)`, for `(valid, reply)`.
When the client sends an invalid message, it will send `(1337,0)`, for `(invalid, send)`. The server will then mirror
the message code, change the message op to `reply` and return `(1337,1)`, for `(invalid, reply)`.

## Lab setup

We are going to run this lab on a CentOS 9 Stream system.

For starters, add the contents of [bashrc](bashrc) to your `~/.bashrc` and then run `source ~/.bashrc`:

Next, set up 2 namespaces `red` and `blue`, and in there hosts `192.168.123.11/24` and `192.168.124.11/24`.
Run file [setup_lab.sh](setup_lab.sh) to do so:
```
./setup_lab.sh
```

Load the [nft ruleset](ruleset.nft):
```
nft -f ruleset.nft
```

Next, create a python virtual environment, activate it and install scapy. You must activate the venv whenever you want
to run the client or server process:
```
virtualenv scapy
source scapy/bin/activate
pip install scapy
```

Open one terminal for the `red` namespace, and one terminal for the `blue` namespace:
```
[root@centos9 ~]# ip netns exec red bash
(red) [root@centos9 ~]# ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
5: red@if6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether d2:55:14:95:35:ce brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 192.168.123.11/24 scope global red
       valid_lft forever preferred_lft forever
    inet6 fe80::d055:14ff:fe95:35ce/64 scope link 
       valid_lft forever preferred_lft forever
(red) [root@centos9 ~]# ip r
default via 192.168.123.1 dev red 
192.168.123.0/24 dev red proto kernel scope link src 192.168.123.11
```

```
[root@centos9 ~]# ip netns exec blue bash
(blue) [root@centos9 ~]# ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
7: blue@if8: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 0e:56:71:e3:69:7b brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 192.168.124.11/24 scope global blue
       valid_lft forever preferred_lft forever
    inet6 fe80::c56:71ff:fee3:697b/64 scope link 
       valid_lft forever preferred_lft forever
(blue) [root@centos9 ~]# ip r
default via 192.168.124.1 dev blue 
192.168.124.0/24 dev blue proto kernel scope link src 192.168.124.11
```

Run the server inside the `red` namespace, and connect to it from the `blue` namespace:
```
(red) [root@centos9 ~]# source scapy/bin/activate
(scapy) (red) [root@centos9 ~]# ./client_server.py -l 192.168.123.11:9999
Starting server with IP 192.168.123.11 and port 9999
```

```
(scapy) (blue) [root@centos9 ~]# ./client_server.py -c 192.168.123.11:9999 
Sending  message to   ('192.168.123.11', 9999) with op '0' and message code '1'
Received message from ('192.168.123.11', 9999) with op '1' and message code '1'
(scapy) (blue) [root@centos9 ~]# ./client_server.py -c 192.168.123.11:9999 -i
Sending  message to   ('192.168.123.11', 9999) with op '0' and message code '1337'
Received message from ('192.168.123.11', 9999) with op '1' and message code '1337'
```

## Using NFT raw payload expressions to filter traffic

We can insert a raw payload expressions to filter traffic based on custom protocol fields. First, let's have a look
at the man page for nft:
```
man nft
(...)
   RAW PAYLOAD EXPRESSION
           @base,offset,length

       The raw payload expression instructs to load length bits starting at offset bits. Bit 0 refers to
       the very first bit — in the C programming language, this corresponds to the topmost bit, i.e. 0x80
       in case of an octet. They are useful to match headers that do not have a human-readable template
       expression yet. Note that nft will not add dependencies for Raw payload expressions. If you e.g.
       want to match protocol fields of a transport header with protocol number 5, you need to manually
       exclude packets that have a different transport header, for instance by using meta l4proto 5 before
       the raw expression.

       Table 54. Supported payload protocol bases
       ┌─────┬─────────────────────────────────────┐
       │Base │ Description                         │
       ├─────┼─────────────────────────────────────┤
       │     │                                     │
       │ll   │ Link layer, for example the         │
       │     │ Ethernet header                     │
       ├─────┼─────────────────────────────────────┤
       │     │                                     │
       │nh   │ Network header, for example IPv4 or │
       │     │ IPv6                                │
       ├─────┼─────────────────────────────────────┤
       │     │                                     │
       │th   │ Transport Header, for example TCP   │
       └─────┴─────────────────────────────────────┘

       Matching destination port of both UDP and TCP.

           inet filter input meta l4proto {tcp, udp} @th,16,16 { 53, 80 }

       The above can also be written as

           inet filter input meta l4proto {tcp, udp} th dport { 53, 80 }

       it is more convenient, but like the raw expression notation no dependencies are created or checked.
       It is the users responsibility to restrict matching to those header types that have a notion of
       ports. Otherwise, rules using raw expressions will errnously match unrelated packets, e.g.
       mis-interpreting ESP packets SPI field as a port.

       Rewrite arp packet target hardware address if target protocol address matches a given address.

           input meta iifname enp2s0 arp ptype 0x0800 arp htype 1 arp hlen 6 arp plen 4 @nh,192,32 0xc0a88f10 @nh,144,48 set 0x112233445566 accept
(...)
```

In our concrete case, this means that we can insert a custom rule that inspects the first 16 bits (the `message_code`
field) of our custom protocol. And if the message code is `MESSAGE_CODE_INVALID` = `1337`, we can drop these packets:
```
nft insert rule table-ip-filter chain-forward meta l4proto udp @th,64,16 1337 counter drop
```

```
(scapy) (blue) [root@centos9 ~]# timeout 5 ./client_server.py -c 192.168.123.11:9999
Sending  message to   ('192.168.123.11', 9999) with op '0' and message code '1'
Received message from ('192.168.123.11', 9999) with op '1' and message code '1'
(scapy) (blue) [root@centos9 ~]# timeout 5 ./client_server.py -c 192.168.123.11:9999 -i
Sending  message to   ('192.168.123.11', 9999) with op '0' and message code '1337'
(scapy) (blue) [root@centos9 ~]#
```

This will block any invalid message. But let's say we only wanted to block invalid reply messages from the server.

First, delete the rule which we just created:
```
(scapy) [root@centos9 ~]# nft --handle -n list ruleset
table ip table-ip-filter { # handle 11
	chain chain-forward { # handle 1
		type filter hook forward priority 0; policy drop;
		@th,64,16 0x539 counter packets 3 bytes 96 drop # handle 6
(...)
(scapy) [root@centos9 ~]# nft delete rule table-ip-filter chain-forward handle 6
```

And insert the correct rule:
```
nft insert rule table-ip-filter chain-forward meta l4proto udp @th,64,16 1337 @th,80,16 1 counter drop
```

Whereas the client never receives the reply ...
```
(scapy) (blue) [root@centos9 ~]# timeout 5 ./client_server.py -c 192.168.123.11:9999 -i
Sending  message to   ('192.168.123.11', 9999) with op '0' and message code '1337'
(scapy) (blue) [root@centos9 ~]# 
```

... both the server output ...
```
(scapy) (red) [root@centos9 ~]# ./client_server.py -l 192.168.123.11:9999
Starting server with IP 192.168.123.11 and port 9999
RECEIVED INVALID CODE:
Received message from ('192.168.124.11', 45864) with op '0' and message code '1337'
Sending  message to   ('192.168.124.11', 45864) with op '1' and message code '1337'
```

... and a tcpdump in the default namespace reveal that the request makes it all the way from the client to the server,
whereas the reply is filtered by nftables:
```
[root@centos9 ~]# tcpdump -nne -i os-red
dropped privs to tcpdump
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on os-red, link-type EN10MB (Ethernet), snapshot length 262144 bytes
11:14:59.295145 42:71:a2:69:ab:15 > d2:55:14:95:35:ce, ethertype IPv4 (0x0800), length 46: 192.168.124.11.56608 > 192.168.123.11.9999: UDP, length 4
11:14:59.295355 d2:55:14:95:35:ce > 42:71:a2:69:ab:15, ethertype IPv4 (0x0800), length 46: 192.168.123.11.9999 > 192.168.124.11.56608: UDP, length 4
```

We can also see that the nftables counters increased:
```
(scapy) [root@centos9 ~]# nft -n --handle list ruleset | grep th,
		@th,64,32 0x5390001 counter packets 1 bytes 32 drop # handle 7
```
