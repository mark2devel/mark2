import termios
import term_raw

class Prompt:
    text = ''
    prefix = '% '
    cursor = 0
    
    history = ['']
    history_pos = 0
    tab_old = None
    tab_accepted = True
    tab_index = 0
    
    def __init__(self, callback_refresh, callback_enter, callback_tab, callback_switch):
        self.callback_refresh = callback_refresh
        self.callback_enter = callback_enter
        self.callback_tab = callback_tab
        self.callback_switch = callback_switch
        self.echo = term_raw.TermMode((3, termios.ECHO), (3, termios.ICANON))
        self.echo.disable()
    
    def clean_up(self):
        self.echo.enable()
    
    def save_prompt(self):
        self.history[self.history_pos] = self.text
    
    def load_prompt(self):
        self.set_prompt(self.history[self.history_pos])
    
    def set_prompt(self, text):
        self.text = text
        self.cursor = len(self.text)
        self.callback_refresh()
    
    def __repr__(self):
        #Write prompt
        o = self.prefix + self.text
        
        #Position cursor
        o += '\r' + '\x1B[C' * (len(self.prefix)+self.cursor)
        
        return o
        
    def write(self, data):
        for ty, key in term_raw.decode(data):
            if ty == term_raw.TYPE_CHAR:
                self.text = self.text[:self.cursor] + key + self.text[self.cursor:]
                self.cursor +=1
                self.tab_accepted = True
                self.tab_index = 0
            else:
                self.write_special_key(key)
        self.callback_refresh()
    
    def write_special_key(self, key):
        
        tab = False
        
        ### Delete/backspace
        if key == 'delete':
            self.text = self.text[:self.cursor] + self.text[self.cursor+1:]
        
        elif key == 'backspace':
            if self.cursor > 0:
                self.cursor -= 1
                self.text = self.text[:self.cursor] + self.text[self.cursor+1:]
        
        ### Cursor left/right
        elif key == 'arrow_left':
            self.cursor = max(self.cursor-1, 0)
        elif key == 'arrow_right':
            self.cursor = min(self.cursor+1, len(self.text))
        
        ### Home/end
        elif key == 'home':
            self.cursor = 0
        elif key == 'end':
            self.cursor = len(self.text)
        
        ### Scrollback (cursor up/down)
        elif key == 'arrow_up':
            if self.history_pos > 0:
                self.save_prompt()
                self.history_pos -= 1
                self.load_prompt()
        elif key == 'arrow_down':
            if self.history_pos < len(self.history)-1:
                self.save_prompt()
                self.history_pos += 1
                self.load_prompt()
        
        ### Tab
        elif key == 'tab':
            if self.tab_accepted:
                self.tab_accepted = False
                self.tab_old = self.text
                self.callback_tab(self.text, self.tab_index)
            else:
                self.callback_tab(self.tab_old, self.tab_index)
            self.tab_index += 1
            tab = True
        
        ### Enter
        elif key == 'enter':
            self.callback_enter(self.text)
            self.history_pos = len(self.history) - 1
            if self.history[self.history_pos-1] == self.text:
                self.text = ''
                self.cursor = 0
                self.save_prompt()
            else:
                self.save_prompt()
                self.history.append('')
                self.history_pos += 1
                self.load_prompt()
        
        ### server switch
        elif key == 'control_right':
            self.callback_switch(1)
        elif key == 'control_left':
            self.callback_switch(-1)
        
        if not tab:
            self.tab_accepted = True
            self.tab_index = 0
        
