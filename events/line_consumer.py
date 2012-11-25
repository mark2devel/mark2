from events import Line

class LineConsumer(Line):
    handle_once = True
    dispatch_once = True
