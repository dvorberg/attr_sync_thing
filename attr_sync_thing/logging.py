import sys, logging, logging.handlers

from .configuration import configuration

try:
    from termcolor import colored
    from io import StringIO
  
    def cprint(*args, color="red", **kw):        
        if "file" in kw:
            file=kw["file"]
            del kw["file"]
        else:
            file=sys.stderr

        if file.isatty():            
            fp = StringIO()        
            print(*args, file=fp, **kw)        
            print(colored(fp.getvalue(), color), file=file, end="")
        else:
            print(*args, file=file, **kw)

    class ColoredStdStreamHandler(logging.StreamHandler):
        level_to_color = {
            logging.CRITICAL: 'dark red',
            logging.ERROR: 'red',
            logging.WARNING: 'yellow',
            logging.INFO: 'cyan',
            logging.DEBUG: 'grey',
            logging.NOTSET: 'black',
        }
        
        def __init__(self, stream=None):
            logging.StreamHandler.__init__(self, stream)

            if self.stream.isatty():
                # Only print messages.
                self.setFormatter(logging.Formatter("%(message)s"))

                # Replace self.emit()
                self.emit = self.emit_colorfully
            
            
        def emit_colorfully(self, record):
            msg = self.format(record)
            color = self.level_to_color.get(record.levelno, 0)
            if color != "black":
                self.stream.write(colored(msg, color) + self.terminator)
            else:
                self.stream.write(msg + self.terminator)
            self.flush()

    StdStreamHandler = ColoredStdStreamHandler
except ImportError:
    StdStreamHandler = logging.StreamHandler

def init_logging():       
    level = logging.WARNING
    
    if configuration.info:
        level = logging.INFO
    if configuration.debug:
        level = logging.DEBUG

    std_stream_handler = StdStreamHandler()
    
    handlers = [ std_stream_handler, ]

    if configuration.logfile_path:
        logfile_handler = logging.handlers.RotatingFileHandler(
            str(configuration.logfile_path),
            maxBytes=100*1024*1024,
            backupCount=5)
        # Logfile entries contain a timestamp and the log level.
        logfile_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"))
        
        handlers.append(logfile_handler)
    
    logging.basicConfig(handlers=handlers, level=level) #force=True, 

    # Turn off watchdog’s event logging.
    if not configuration.log_watchdog_events:
        fs_event_logger = logging.getLogger('fsevents')
        fs_event_logger.level = logging.CRITICAL
        

    

debug = logging.debug
info = logging.info
warning = logging.warning
error = logging.error
