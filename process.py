from twisted.internet import protocol, reactor
import os
import glob
import subprocess


#nice = self.parent.profile('nice')
#if nice != 0:
#    kwargs['preexec_fn'] = lambda : os.nice(nice)



class ProcessProtocol(protocol.ProcessProtocol):
    obuff = ""
    def __init__(self, parent):
        self.parent = parent
    
    
        self.check_dependencies()
        
    def check_dependencies(self):
        if os.name != 'posix':
            self.parent.fatal_error("this program requires a posix environment (linux, bsd, os x, etc)")
        if not self.check_executable('java'):
            self.parent.fatal_error("couldn't find java executable")
        #if not self.check_executable('socat'):
        #    self.parent.fatal_error("couldn't find socat executable")

    def check_executable(self, name):
        return self.find_executable(name) != ''

    def find_executable(self, name):
        return subprocess.check_output(['which', name]).strip()

    def find_jar(self):
        candidates = glob.glob('craftbukkit*.jar') + glob.glob('minecraft_server.jar')
        if candidates:
            return candidates[0]
        else:
            self.parent.fatal_error("Couldn't locate a server jar!")

    def build_command(self):
        cmd = []
        cmd.append(self.find_executable('java'))
        cmd.extend(self.parent.cfg.get_jvm_options())
        cmd.append('-jar')
        cmd.append(self.find_jar())
        cmd.append('nogui')
        return cmd
    
    
    def errReceived(self, data):
        data = data.split("\n")
        data[0] = self.obuff + data[0]
        self.obuff = data.pop()
        for l in data:
            self.parent.p_out(l)
    
    def processEnded(self, reason):
        self.parent.p_stop()
    

def Process(parent):
    proto = ProcessProtocol(parent)
    cmd   = proto.build_command()
    return proto, reactor.spawnProcess(proto, cmd[0], cmd)

def get_usage(pid):
    c = ['ps', '-p', str(pid), '-o', 'pcpu=', '-o', 'vsz=']
    try:
        out = subprocess.check_output(c).strip().split(" ")
    except subprocess.CalledProcessError:
        out = ("0", "0")
    
    return {
        'cpu': float(out[0]),
        'mem': int(out[1])
    }

