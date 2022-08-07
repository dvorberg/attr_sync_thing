import pathlib, time

class ModificationManager(object):
    """
    Keep track of file modifications we make. 
    """

    # Modification made within this time are considered to have been made
    # by ourselves and are to be ignored by the watchdog event handler.
    modification_timeout = 1.0
    
    def __init__(self):
        self.modifications = {}

    def register_modification(self, path:pathlib.Path):
        path = path.resolve()
        self.modifications[path] = time.time()

    def did_we_modify(self, path):
        path = path.resolve()
        
        now = time.time()

        t = self.modifications.get(path, None)
        if t is None:
            ret = False
        else:
            if now - t < self.modification_timeout:
                ret = True
            else:
                ret = False

            # We ignore the notification about our own modification
            # once. 
            del self.modifications[path]
            
        # Housekeeping
        #for path, mtime in list(self.modifications.items()):
        #    if now - mtime > self.modification_timeout:
        #        del self.modifications[path]

        return ret

modification_manager = ModificationManager()
