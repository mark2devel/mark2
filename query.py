import re
import struct

from twisted.application.internet import UDPServer
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import task

import events

class QueryProtocol(DatagramProtocol):
    interval = 10
    challenge = None
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        
        self.read_string = lambda b: b.split('\x00', 1)
        self.handshake   = lambda:   self.write_packet(9)
        self.stat        = lambda:   self.write_packet(0, self.challenge, '\x00\x00\x00\x00')
    
    def startProtocol(self):
        t = task.LoopingCall(self.handshake)
        t.start(self.interval)
    
    def write_packet(self, type, *payload):
        if self.transport:
            self.transport.write(
                '\xFE\xFD'              + \
                struct.pack('>B', type) + \
                '\x00\x00\x00\x00'      + \
                ''.join(payload),
                addr=(self.host, self.port))
        
    def datagramReceived(self, buff, (host, port)):
        ty = struct.unpack('>B', buff[0])[0]
        
        if ty == 9:
            self.challenge = struct.pack('>I', int(buff[5:-1]))
            self.stat()
        
        if ty == 0:
            o = {'players': []}
            
            #Read K, V
            buff = buff[16:]
            while True:
                #Read K
                k, buff = self.read_string(buff)
                if k == '':
                    break
                
                #Read V
                v, buff = self.read_string(buff)
                
                #Parse V and store
                if k in ('numplayers', 'maxplayers', 'hostport'):
                    o[k] = int(v)
                elif k == 'plugins':
                    v = v.split(':', 1)
                    o['server_mod'] = v[0]
                    if len(v) == 1:
                        o[k] = []
                    else:
                        o[k] = v[1].split('; ')
                else:
                    o[k] = v
            
            #Read Players
            buff = buff[10:]
            while True:
                p, buff = self.read_string(buff)
                if p == '':
                    break
                p = re.sub('\xa7.{1}', '', p)
                o['players'].append(p)
            
            self.dispatch(events.StatPlayerCount(source = "query", players_current = o['numplayers'], players_max = o['maxplayers']))
            self.dispatch(events.StatPlayers    (source = "query", players         = o['players']))
            self.dispatch(events.StatPlugins    (source = "query", plugins         = o['plugins']))

class Query(UDPServer):
    name = "query"
    def __init__(self, parent, interval, host, port):
        p = QueryProtocol(host, port)
        p.dispatch = parent.events.dispatch
        p.interval = interval
        UDPServer.__init__(self, 0, p)
