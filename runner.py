import sys
import threading

from autobahn.twisted.websocket import WebSocketServerFactory
from transit.transit_types import Keyword
from twisted.internet import reactor

from simulation import Simulation
from journal import Journal
from websocket import makeVizWebSocketClass

def startRunner(vizModel, port, useBackgroundThread=False):
    journal = Journal(vizModel)
    simulation = Simulation(vizModel)

    localTargets = {
        Keyword("into-sim"): lambda x: simulation.handleMessage(x),
        Keyword("into-journal"): lambda x: journal.handleMessage(x),
    }

    port = 24601
    factory = WebSocketServerFactory("ws://127.0.0.1:{0}".format(port), debug=False)
    factory.protocol = makeVizWebSocketClass(localTargets)
    reactor.listenTCP(port, factory)

    if useBackgroundThread:
        t = threading.Thread(target=reactor.run, kwargs={"installSignalHandlers": 0})
        t.daemon = True
        t.start()
    else:
        reactor.run()
