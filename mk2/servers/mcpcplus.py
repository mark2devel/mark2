from . import JenkinsJarProvider

class MCPCPlus(JenkinsJarProvider):
    name = 'MCPC-Plus'
    base = 'http://ci.md-5.net/'
    project = 'MCPC-Plus'

ref = MCPCPlus
