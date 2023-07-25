#!/usr/bin/env python
'''
Simple implementation of a custom client/server messaging protocol on top of
UDP.
'''

import socket
from ipaddress import ip_address
from optparse import OptionParser

from scapy.all import Packet, ShortField


MESSAGE_OP_SEND = 0
MESSAGE_OP_REPLY = 1

MESSAGE_CODE_VALID = 1
MESSAGE_CODE_INVALID = 1337


class Messenger(Packet):
    '''
    Messenger implements a dummy protocol. The dummy protocol has 2 operations,
    SEND and REPLY. It has to message codes, VALID and INVALID.
    '''
    name = "Messenger"
    fields_desc = [ShortField("message_code", MESSAGE_CODE_INVALID),
                   ShortField("message_op", MESSAGE_OP_SEND)]


def client(ip_addr: str, port: int, message_code: int, message_op: int):
    '''
    client runs the client logic: send a packet to the server and receive
    an answer from it.
    '''
    msg = Messenger(message_code=message_code, message_op=message_op)
    print(f"Sending  message to   {(ip_addr, port)} with op "
          f"'{msg.getfieldval('message_op')}' and message code "
          f"'{msg.getfieldval('message_code')}'")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(bytes(msg), (ip_addr, port))
    data, addr = sock.recvfrom(1024)
    answer = Messenger(data)
    print(f"Received message from {addr} with op "
          f"'{answer.getfieldval('message_op')}' and message code "
          f"'{answer.getfieldval('message_code')}'")


def server(ip_addr: str, port: int):
    '''
    server runs the server logic: for every packet received, send and answer.
    The resulting message_code will be mirrored back to the client.
    '''
    print(f"Starting server with IP {ip_addr} and port {port}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip_addr, port))

    while True:
        data, addr = sock.recvfrom(1024)
        answer = Messenger(data)
        message_code = answer.getfieldval('message_code')

        if message_code == MESSAGE_CODE_INVALID:
            print("RECEIVED INVALID CODE:")
        print(f"Received message from {addr} with op "
              f"'{answer.getfieldval('message_op')}' and message code "
              f"'{message_code}'")
        msg = Messenger(message_code=message_code, message_op=MESSAGE_OP_REPLY)
        print(f"Sending  message to   {addr} with op "
              f"'{msg.getfieldval('message_op')}' and message code "
              f"'{msg.getfieldval('message_code')}'")
        sock.sendto(bytes(msg), addr)


def parse_ip_port(ip_port_str: str):
    '''parse_ip_port takes a string <ip>:<port> and returns (ip_addr, port)'''
    left, sep, right = ip_port_str.rpartition(":")

    if sep != ":":
        raise ValueError("cannot parse <ip>:<port>, invalid string "
                         f"'{ip_port_str}'")
    ip_addr = format(ip_address(left.strip("[]")))
    port = int(right)

    return ip_addr, port


def main():
    '''main program logic'''
    usage = ("Usage: %prog (-l <address>:<port>|-c <address>:<port> "
             "[--code-invalid])")
    parser = OptionParser(usage)
    parser.add_option("-l", "--listen", dest="listen",
                      help="specify the listen address (trigger server mode)")
    parser.add_option("-c", "--connect", dest="connect",
                      help="specify the target address (trigger client mode)")
    parser.add_option("-i", "--code-invalid", action="store_true",
                      default=False, dest="message_code_invalid",
                      help="send an invalid message")

    (options, args) = parser.parse_args()

    if (options.listen is None and options.connect is None
       or options.listen is not None and options.connect is not None):
        parser.error("provide a listen address (server mode) or a connect "
                     "address (client mode)")

    try:
        if options.listen is not None:
            server(*parse_ip_port(options.listen))
        else:
            message_code = MESSAGE_CODE_VALID

            if options.message_code_invalid:
                message_code = MESSAGE_CODE_INVALID
            client(*parse_ip_port(options.connect), message_code,
                   MESSAGE_OP_SEND)
    except ValueError as exception:
        print(f"error: {exception}")


if __name__ == "__main__":
    main()
