import sys
import threading

from autobahn.twisted.websocket import WebSocketServerFactory
from transit.transit_types import Keyword
from twisted.internet import reactor
from twisted.python import log

import marshalling as marshal
from simulation import Simulation
from journal import Journal
from websocket import makeSanityWebSocketClass

class Channel(object):
    def __init__(self, fput, fclose):
        self.put = fput
        self.close = fclose

class SanityRunner(object):
    def __init__(self, sanityModel):
        journal = Journal(sanityModel)
        simulation = Simulation(sanityModel)
        self.localTargets = {
            Keyword("into-sim"): marshal.channel(simulation),
            Keyword("into-journal"): marshal.channel(journal),
        }

    def start(self, port=24601, useBackgroundThread=False):
        factory = WebSocketServerFactory("ws://127.0.0.1:{0}".format(port), debug=False)
        factory.protocol = makeSanityWebSocketClass(self.localTargets, {}, {})
        log.startLogging(sys.stdout)
        reactor.listenTCP(port, factory)

        if useBackgroundThread:
            t = threading.Thread(target=reactor.run, kwargs={"installSignalHandlers": 0})
            t.daemon = True
            t.start()
        else:
            reactor.run()
