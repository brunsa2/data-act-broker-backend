from dataactcore.models.baseInterface import BaseInterface
from dataactbroker.handlers.jobHandler import JobHandler


class InterfaceHolder:
    """ This class holds an interface to each database as a static variable, to allow reuse of connections throughout the project """
    def __init__(self):
        """ Create the interfaces """
        if BaseInterface.interfaces is None:
            self.jobDb = JobHandler()
            BaseInterface.interfaces = self
        else:
            self.jobDb = BaseInterface.interfaces.jobDb

    def close(self):
        """ Close all open connections """
        if self.jobDb is not None:
            self.jobDb.close()
