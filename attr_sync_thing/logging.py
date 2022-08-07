import sys

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

        
except ImportError:
    def cprint(*args, color=None, **kw):
        print(*args, **kw)

def debug(*args):
    """
    Step-by-step what’s going on, for debugging purposes. Goes to stdout.    
    """
    if configuration.debug:
        print(*args, file=sys.stderr)

def info(*args):    
    """
    General information. Used for the startup message
    """
    cprint(*args, color="cyan", file=sys.stderr)

def warning(*args):    
    """
    Things that might need user interference.
    """
    cprint(*args, color="yellow", file=sys.stderr)

def error(*args):
    """
    The program making valid excuses, why something didn’t work as
    expected. 
    """
    cprint(*args, color="red", file=sys.stderr)
    
