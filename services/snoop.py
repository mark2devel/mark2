#patching
from os         import chdir, getcwd
from tempfile   import mkdtemp
from shutil     import rmtree
from struct     import pack
from subprocess import check_output

#server
import re
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.application.service import Service
from twisted.internet import reactor

import events

def jar_contents(j_path):
    return check_output(['jar', 'tf', j_path]).split("\n")

def jar_extract(j_path):
    return check_output(['jar', 'xf', j_path])

def jar_update(j_path, t_path, c_path):
    c_path = c_path[len(t_path)+1:]
    return check_output(['jar', 'uf', j_path, '-C', t_path, c_path])

def jlong(v):
    return pack('>q', v)

def jstring(v):
    return "%s%s" % (pack('>h', len(v)), v)

def jurl(h, p):
    p = "" if p == 80 else ":%d" % p
    return jstring("http://%s%s/" % (h,p))

def patch(j_path, host, port, interval):
    #Marker file to put in jar
    m_name = '.snooper-patched'
    
    #Get jar contents
    j_contents = jar_contents(j_path)

    #Make a temporary directory
    t_path = mkdtemp(prefix='mark2-patch-')
    
    o_path = getcwd()
    chdir(t_path)
    
    #Extract the jar
    jar_extract(j_path)
    
    #Figure out what we need to replace
    if m_name in j_contents:
        f = open("%s/%s" % (t_path, m_name), "r")
        old_host, old_port, old_interval = f.read().split("\n")
        old_port = int(old_port)
        old_interval = int(old_interval)
        f.close()
    else:
        old_host, old_port, old_interval = 'snoop.minecraft.net', 80, 900000
    
    replace = {
        jlong(old_interval): jlong(interval),
        jurl(old_host, old_port): jurl(host, port)}
    
    #Find the relevant class
    c_path = None
    c_data = None
    
    for name in j_contents:
        name = "%s/%s" % (t_path, name)
        if not name.endswith(".class"):
            continue
        
        f = open(name, 'r')
        data = f.read()
        f.close()
        
        found = True
        for k in replace.keys():
            found &= data.find(k) != -1
        
        if found:
            c_path = name
            c_data = data
            break
    
    #Patch if found
    if c_path != None:
        #Update file contents
        for find, replace in replace.iteritems():
            c_data = c_data.replace(find, replace)
        
        #Write to file
        f = open(c_path, 'wb')
        f.write(c_data)
        f.close()
        
        #Update jar
        jar_update(j_path, t_path, c_path)
        
        #Add marker that it's been patched
        m_path = "%s/%s" % (t_path, m_name)
        f = open(m_path, "w")
        f.write("%s\n%d\n%d" % (host, port, interval))
        f.close()
        jar_update(j_path, t_path, m_path)
    
    rmtree(t_path)
    chdir(o_path)
    return c_path != None

class SnoopResource(Resource):
    isLeaf = True
    def render_POST(self, request):
        worlds = {}
        player_count = {}
        memory = {}
        world_count = 0
        for k, v in request.args.iteritems():
            m = re.match('world\[(\d+)\]\[(.*)\]', k)
            if m:
                i, k2 = m.groups()
                
                if not int(i) in worlds:
                    worlds[int(i)] = {}
                worlds[int(i)][k2] = v[0]
            
            elif k == 'avg_tick_ms':
                self.dispatch(events.StatTickTime(source="snoop", tick_time=int(v[0])))
            elif k in ('players_current', 'players_max'):
                player_count[k] = int(v[0])
            elif k in ('memory_free', 'memory_max'):
                memory[k] = int(v[0])/(1024**2)
        worlds2 = []
        i = 0
        while i in range(world_count):
            worlds2.append(worlds[i])
            i+=1
        
        if worlds2:
            self.dispatch(events.StatWorlds(source="snoop", worlds=worlds))
        
        if len(player_count) == 2:
            self.dispatch(events.StatPlayerCount(source="snoop", **player_count))
        if len(memory) == 2:
            memory['memory_current'] = memory['memory_max'] - memory['memory_free']
            del memory['memory_free']
            self.dispatch(events.StatMemory(source="snoop", **memory))

class SnoopSite(Site):
    def log(self, request):
        pass

class Snoop(Service):
    def __init__(self, parent, interval, jarfile, start_server):
        self.parent       = parent
        self.interval     = interval
        self.jarfile      = jarfile
        self.start_server = start_server
        
        self.listeningPort = None
        
        resource = SnoopResource()
        resource.dispatch = self.parent.events.dispatch
        
        self.factory = SnoopSite(resource)
    
    def privilegedStartService(self):
        self.listeningPort = reactor.listenTCP(0, self.factory)
        result = patch(
            self.jarfile, 
            "localhost", 
            self.listeningPort.getHost().port, 
            self.interval)
        
        if result:
            self.start_server.callback(0)
        else:
            self.start_server.errback(ValueError("couldn't patch server jar!")) #TODO: review.
        
        return Service.privilegedStartService(self)
    
    def stopService(self):
        if self.listeningPort:
            self.listeningPort.stopListening()
        return Service.stopService(self)
