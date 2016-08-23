#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import standard python modules
import argparse
import json
import logging
import platform
import re
import socket
import struct
import time

from influxdb import InfluxDBClient

# Change these values for your environment
DB_HOST = '127.0.0.1'
DB_PORT = 8086
DB_NAME = 'mcast'
DB_USER = 'root'
DB_PASS = 'root'
INTER_PKT_INTERVAL = 0.1
REPORT_INTERVAL = 5
TTL = 8

class MulticastClient():
    group = ''                      # Multicast group
    interval = INTER_PKT_INTERVAL   # Inter-packet interval
    ttl = TTL                       # TTL
    port = ''                       # UDP port
    def __init__(self, group, port):
        self.group = group
        self.port = port
        logging.info('Starting as client, group = %s, port = %s' % (self.group, self.port))
    def send(self):
        logging.info('Sending packets...')
        seq_num = 1
        addrinfo = socket.getaddrinfo(self.group, None)[0]
        s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

        # Set Time-to-live (optional)
        ttl_bin = struct.pack('@i', self.ttl)
        if addrinfo[0] == socket.AF_INET: # IPv4
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl_bin)
        else:
            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, ttl_bin)

        while True:
            data = 'seq_num=%d' % seq_num
            s.sendto(data + '\0', (addrinfo[4][0], self.port))
            time.sleep(self.interval)
            logging.debug('Sending packet to %s, seq_num = %d' % (self.group, seq_num))
            seq_num = seq_num + 1


class MulticastServer():
    group = ''                      # Multicast group
    db_host = DB_HOST               # InfluxDB host name
    db_port = DB_PORT               # InfluxDB server port
    db_name = DB_NAME               # InfluxDB database name
    db_user = DB_USER               # InfluxDB username
    db_pass = DB_PASS               # InfluxDB password
    interval = REPORT_INTERVAL      # Logging interval
    def __init__(self, group, port):
        self.group = group
        self.port = port
        logging.info('Starting as server, group = %s, port = %s' % (self.group, self.port))
    def receive(self):
        logging.info('Receiving packets...')
        seq_num = 1             # Sequence number inside packet received
        last_seq_num = 0        # Sequence number from the last packet
        first_packet = True     # Is this the first packet we are receiving
        total_good = 0          # Good packets
        total_received = 0      # Received (including invalid)
        total_lost = 0          # Lost (derived from calculation)
        total_invalid = 0       # Invalid
        
        # Look up multicast group address in name server and find out IP version
        addrinfo = socket.getaddrinfo(self.group, None)[0]

        # Create a socket
        s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

        # Allow multiple copies of this program on one machine
        # (not strictly needed)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind it to the port
        s.bind(('', self.port))

        if platform.system() == 'Windows':
            group_bin = socket.inet_aton(addrinfo[4][0])
        else:
            group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
        # Join group
        if addrinfo[0] == socket.AF_INET: # IPv4
            mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        else:
            mreq = group_bin + struct.pack('@I', 0)
            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

        report_step = time.time()

        # Loop, printing any data we receive
        while True:
            if time.time() > report_step + self.interval:
                logging.debug('Report: %d total, %d lost, %d invalid, %d good' % (total_received, total_lost, total_invalid, total_good))
                
                json_body = [
                    {
                        'measurement': 'traffic',
                        'tags': {
                            'group': self.group,
                        },
                        'fields': {
                            'total_received': total_received,
                            'total_good': total_good,
                            'total_invalid': total_invalid,
                            'total_lost': total_lost,
                        },
                    }
                ]
                try:
                    client = InfluxDBClient(self.db_host, self.db_port, self.db_user, self.db_pass, self.db_name)
                    client.write_points(json_body)
                except:
                    pass

                report_step = time.time()
                total_received = 0
                total_good = 0
                total_invalid = 0
                total_lost = 0

            data, sender = s.recvfrom(1500)
            while data[-1:] == '\0': data = data[:-1] # Strip trailing \0's
            try:
                seq_num = int(re.match(r'^seq_num=(\d+)', data).group(1))
            except AttributeError:
                pass
            except:
                raise
            if seq_num and first_packet:
                logging.debug('Received first packet from %s, seq_num = %d' % (sender, seq_num))
                last_seq_num = seq_num
                total_good = total_good + 1
            elif seq_num == last_seq_num + 1:
                logging.debug('Received packet from %s, seq_num = %d' % (sender, seq_num))
                last_seq_num = seq_num
                total_good = total_good + 1
            elif seq_num:
                logging.warn('Received packet with invalid seq_num from %s, seq_num = %d, delta = %d' % (sender, seq_num, seq_num - last_seq_num))   
                total_lost = total_lost + (seq_num - last_seq_num + 1)
                total_received = total_received + (seq_num - last_seq_num)
                last_seq_num = seq_num
            else:
                logging.warn('Received invalid packet from %s, port %d, payload = %s' % (sender, data))
                total_invalid = total_invalid + 1
            first_packet = False
            total_received = total_received + 1

def main(args, loglevel):
    # Logging format
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=loglevel)

    # Client
    if args.client:
        client = MulticastClient(args.group, args.port)
        client.send()
    # Server
    else:
        server = MulticastServer(args.group, args.port)
        server.receive()

if __name__ == '__main__':
    # Setup parser    
    parser = argparse.ArgumentParser(
        description='Multicast troubleshooting tool with InfluxDB output',
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', '--client', help='Client', action='store_true')
    group.add_argument('-s', '--server', help='Server', action='store_true')
    parser.add_argument('-p', '--port', type=int, required=True, help='UDP port')
    parser.add_argument('group', help='Multicast group')
    parser.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO

    main(args, loglevel)