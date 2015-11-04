import datetime
import threading
from collections import deque

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import runner

from nupic.data.inference_shifter import InferenceShifter
from nupic.frameworks.opf.metrics import MetricSpec
from nupic.frameworks.opf.modelfactory import ModelFactory
from nupic.frameworks.opf.predictionmetricsmanager import MetricsManager

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.dates import date2num, DateFormatter

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
    from swarmed_model_params import MODEL_PARAMS
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

    WINDOW = 100
    dates = deque(maxlen=WINDOW)
    convertedDates = deque(maxlen=WINDOW)
    actualValues = deque([0.0] * WINDOW, maxlen=WINDOW)
    predictedValues = deque([0.0] * WINDOW, maxlen=WINDOW)
    actualLines = None
    predictedLines = None
    linesInitialized = False
    plotCount = 1
    fig = plt.figure(figsize=(6.1, 11))
    gs = gridspec.GridSpec(plotCount, 1)
    graph = fig.add_subplot(gs[0, 0])
    plt.xlabel('Date')
    plt.ylabel('Consumption (kW)')
    plt.tight_layout()

    shifter = InferenceShifter()
    metricsManager = MetricsManager(_METRIC_SPECS, model.getFieldInfo(),
                                    model.getInferenceType())
    counter = 0

    shouldScheduleDraw = True

    def draw():
        global shouldScheduleDraw, graph
        shouldScheduleDraw = True
        graph.relim()
        graph.autoscale_view(True, True, True)
        plt.draw()
        plt.legend(('actual', 'predicted'), loc=3)

    def step():
        global dates, convertedDates, actualValues, predictedValues, \
            linesInitialized, actualLines, predictedLines, shouldScheduleDraw, \
            counter, metricsManager
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

        result = shifter.shift(result)
        prediction = result.inferences["multiStepBestPredictions"][1]

        if not linesInitialized:
            dates += deque([timestamp]*WINDOW)
            convertedDates += [date2num(date) for date in dates]

            addedLinesActual, = graph.plot(
                dates, actualValues, 'r'
            )
            actualLines = addedLinesActual

            predictedLinesActual, = graph.plot(
                dates, predictedValues, 'b'
            )
            predictedLines = predictedLinesActual
            graph.xaxis.set_major_formatter(DateFormatter("%H:%M"))
            linesInitialized = True

        dates.append(timestamp)
        convertedDates.append(date2num(timestamp))
        actualValues.append(consumption)
        predictedValues.append(prediction)

        actualLines.set_xdata(convertedDates)
        actualLines.set_ydata(actualValues)
        predictedLines.set_xdata(convertedDates)
        predictedLines.set_ydata(predictedValues)

        if shouldScheduleDraw:
            # If we're stepping the model really quickly, coalesce the redraws.
            shouldScheduleDraw = False
            t = threading.Timer(0.2, draw)
            t.start()

        return (model, [
            ["time", timestampStr],
            ["power consumption (kW)", consumptionStr],
        ])

    runner.startRunner(model, step, 24601, useBackgroundThread=True)
    plt.show()
