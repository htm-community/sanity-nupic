import datetime

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

from simulation import Simulation
from journal import Journal
from websocket import runnerWebSocketProtocol
from swarmed_model_params import MODEL_PARAMS

def startRunner(model, stepfn):
    journal = Journal(model)
    journal.append(model)

    from transit.transit_types import Keyword
    localTargets = {
        Keyword("into-sim"): lambda x: simulation.handleMessage(x),
        Keyword("into-journal"): lambda x: journal.handleMessage(x),
    }

    simulation = Simulation(journal, stepfn)

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

from nupic.frameworks.opf.metrics import MetricSpec
from nupic.frameworks.opf.predictionmetricsmanager import MetricsManager

_METRIC_SPECS = (
    MetricSpec(field='kw_energy_consumption', metric='multiStep',
               inferenceElement='multiStepBestPredictions',
               params={'errorMetric': 'aae', 'window': 1000, 'steps': 1}),
    MetricSpec(field='kw_energy_consumption', metric='trivial',
               inferenceElement='prediction',
               params={'errorMetric': 'aae', 'window': 1000, 'steps': 1}),
    MetricSpec(field='kw_energy_consumption', metric='multiStep',
               inferenceElement='multiStepBestPredictions',
               params={'errorMetric': 'altMAPE', 'window': 1000, 'steps': 1}),
    MetricSpec(field='kw_energy_consumption', metric='trivial',
               inferenceElement='prediction',
               params={'errorMetric': 'altMAPE', 'window': 1000, 'steps': 1}),
)

if __name__ == '__main__':
    from nupic.frameworks.opf.modelfactory import ModelFactory
    model = ModelFactory.create(MODEL_PARAMS)
    model.enableInference({"predictedField": "kw_energy_consumption"})

    import os
    inputPath = os.path.join(os.path.dirname(__file__),
                             "data/rec-center-hourly.csv")

    import csv
    inputFile = open(inputPath, "rb")
    csvReader = csv.reader(inputFile)
    csvReader.next()
    csvReader.next()
    csvReader.next()

    metricsManager = MetricsManager(_METRIC_SPECS, model.getFieldInfo(),
                                    model.getInferenceType())
    counter = 0

    def step():
        global counter, metricsManager
        counter += 1
        timestampStr, consumptionStr = csvReader.next()
        timestamp = datetime.datetime.strptime(timestampStr, "%m/%d/%y %H:%M")
        consumption = float(consumptionStr)
        result = model.run({
            "timestamp": timestamp,
            "kw_energy_consumption": consumption,
        })
        result.metrics = metricsManager.update(result)

        if counter % 100 == 0:
            print "Read %i lines..." % counter
            print ("After %i records, 1-step altMAPE=%f" % (
                counter,
                result.metrics["multiStepBestPredictions:multiStep:"
                               "errorMetric='altMAPE':steps=1:window=1000:"
                               "field=kw_energy_consumption"]))

        return (model, [
            ["time", timestampStr],
            ["power consumption (kW)", consumptionStr],
        ])

    startRunner(model, step)
