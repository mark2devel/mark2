import sys
import tty
import termios
import fcntl
import os
import re

TYPE_CHAR = 1
TYPE_SPECIAL = 2

keys = {
    '\x1B[A' : 'arrow_up',
    '\x1B[B' : 'arrow_down',
    '\x1B[C' : 'arrow_right',
    '\x1B[D' : 'arrow_left',
    '\x1BOH' : 'home',
    '\x1BOF' : 'end',
    '\x1B[1~': 'home',
    '\x1B[3~': 'delete',
    '\x1B[4~': 'end'
}

class TermMode:
    when = termios.TCSANOW
    def __init__(self, *modes):
        self.modes = modes
        self.enable  = lambda: self.switch(True)
        self.disable = lambda: self.switch(False)
    
    def switch(self, enable):
        if enable:
            act = lambda a, b: a | b
        else:
            act = lambda a, b: a & ~b
        
        fd = sys.stdin.fileno()
        x = termios.tcgetattr(fd)[:]
        
        for i, m in self.modes:
            x[i] = act(x[i], m)
        
        termios.tcsetattr(fd, self.when, x)

def decode_char(s):
    if s[0] == '\x1B':
        for sequence, name in keys.iteritems():
            if s.startswith(sequence):
                return s[len(sequence):], TYPE_SPECIAL, name
        
        return s, None, None
    
    if s[0] == '\x7F':
        return s[1:], TYPE_SPECIAL, 'backspace'
    
    if s[0] == '\n':
        return s[1:], TYPE_SPECIAL, 'enter'
    
    if s[0] == '\t':
        return s[1:], TYPE_SPECIAL, 'tab'
    
    if s[0] >= 0x20:
        return s[1:], TYPE_CHAR, s[0]
    
    return s, None, None

def decode(s):
    while len(s) > 0:
        s, ty, v = decode_char(s)
        if ty == None:
            return
        yield (ty, v)

def strip_colors(s):
    return re.sub('\x1B\[\d+m', '', s)
