from os         import chdir
from tempfile   import mkdtemp
from shutil     import rmtree
from struct     import pack
from subprocess import check_output

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
    return c_path != None
