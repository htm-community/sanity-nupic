from simulation import Simulation
from journal import Journal
from websocket import runnerWebSocketProtocol
from swarmed_model_params import MODEL_PARAMS

if __name__ == '__main__':
    from nupic.frameworks.opf.modelfactory import ModelFactory
    model = ModelFactory.create(MODEL_PARAMS)
    model.enableInference({"predictedField": "kw_energy_consumption"})

    journal = Journal(model)
    journal.append(model)

    import csv
    inputFile = open("data/rec-center-hourly.csv", "rb")
    csvReader = csv.reader(inputFile)
    csvReader.next()
    csvReader.next()
    csvReader.next()

    simulation = Simulation(model, journal, csvReader)

    from transit.transit_types import Keyword
    localTargets = {
        Keyword("into-sim"): lambda x: simulation.handleMessage(x),
        Keyword("into-journal"): lambda x: journal.handleMessage(x),
    }

    import sys
    from twisted.python import log
    log.startLogging(sys.stdout)

    from autobahn.twisted.websocket import WebSocketServerFactory
    port = 24601
    factory = WebSocketServerFactory("ws://127.0.0.1:{0}".format(port), debug=False)
    factory.protocol = runnerWebSocketProtocol(localTargets)

    from twisted.internet import reactor
    reactor.listenTCP(port, factory)
    reactor.run()
