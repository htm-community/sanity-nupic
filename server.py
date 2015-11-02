import datetime
import threading
from collections import deque

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

    t = threading.Thread(target=reactor.run, kwargs={"installSignalHandlers": 0})
    t.daemon = True
    t.start()

from nupic.data.inference_shifter import InferenceShifter

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.dates import date2num

if __name__ == '__main__':
    from nupic.frameworks.opf.modelfactory import ModelFactory
    model = ModelFactory.create(MODEL_PARAMS)
    model.enableInference({"predictedField": "kw_energy_consumption"})

    import csv
    inputFile = open("data/rec-center-hourly.csv", "rb")
    csvReader = csv.reader(inputFile)
    csvReader.next()
    csvReader.next()
    csvReader.next()

    WINDOW = 100
    dates = deque(maxlen=WINDOW)
    convertedDates = deque(maxlen=WINDOW)
    actualValues = deque([0.0] * WINDOW, maxlen=WINDOW)
    predictedValues = deque([0.0] * WINDOW, maxlen=WINDOW)
    actualLines = None
    predictedLines = None
    linesInitialized = False
    plotCount = 1
    fig = plt.figure(figsize=(14, 6))
    gs = gridspec.GridSpec(plotCount, 1)
    graph = fig.add_subplot(gs[0, 0])
    plt.title("Marcus")
    plt.xlabel('Date')
    plt.ylabel('Consumption (kW)')
    plt.tight_layout()

    shifter = InferenceShifter()

    shouldScheduleDraw = True

    def draw():
        global shouldScheduleDraw
        shouldScheduleDraw = True
        plt.draw()
        plt.legend(('actual', 'predicted'), loc=3)

    def step():
        global dates, convertedDates, actualValues, predictedValues, \
            linesInitialized, actualLines, predictedLines, shouldScheduleDraw
        timestampStr, consumptionStr = csvReader.next()
        timestamp = datetime.datetime.strptime(timestampStr, "%m/%d/%y %H:%M")
        consumption = float(consumptionStr)
        result = model.run({
            "timestamp": timestamp,
            "kw_energy_consumption": consumption,
        })

        result = shifter.shift(result)
        prediction = result.inferences["multiStepBestPredictions"][1]

        if not linesInitialized:
            dates += deque([timestamp]*WINDOW)
            convertedDates += [date2num(date) for date in dates]

            addedLinesActual, = graph.plot(
                dates, actualValues
            )
            actualLines = addedLinesActual

            predictedLinesActual, = graph.plot(
                dates, predictedValues
            )
            predictedLines = predictedLinesActual
            linesInitialized = True

        dates.append(timestamp)
        convertedDates.append(date2num(timestamp))
        actualValues.append(consumption)
        predictedValues.append(prediction)

        actualLines.set_xdata(convertedDates)
        actualLines.set_ydata(actualValues)
        predictedLines.set_xdata(convertedDates)
        predictedLines.set_ydata(predictedValues)

        graph.relim()
        graph.autoscale_view(True, True, True)

        if shouldScheduleDraw:
            # If we're stepping the model really quickly, coalesce the redraws.
            shouldScheduleDraw = False
            t = threading.Timer(0.2, draw)
            t.start()

        return (model, [
            ["time", timestampStr],
            ["power consumption (kW)", consumptionStr],
        ])

    startRunner(model, step)
    plt.show()
