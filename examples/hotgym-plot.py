import datetime
import csv
import threading
from collections import deque

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import runner
from model import OpfVizModel
from swarmed_model_params import MODEL_PARAMS

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

WINDOW = 100

class HotGym(OpfVizModel):
    def __init__(self, model, inputs):
        super(HotGym, self).__init__(model)
        self.model = model
        self.inputs = inputs
        self.metricsManager = MetricsManager(_METRIC_SPECS, model.getFieldInfo(),
                                             model.getInferenceType())
        self.counter = 0
        self.timestampStr = ""
        self.consumptionStr = ""

        self.shifter = InferenceShifter()

        self.dates = deque(maxlen=WINDOW)
        self.convertedDates = deque(maxlen=WINDOW)
        self.actualValues = deque([0.0] * WINDOW, maxlen=WINDOW)
        self.predictedValues = deque([0.0] * WINDOW, maxlen=WINDOW)
        self.linesInitialized = False
        self.actualLines = None
        self.predictedLines = None
        self.shouldScheduleDraw = True
        fig = plt.figure(figsize=(6.1, 11))
        plotCount = 1
        gs = gridspec.GridSpec(plotCount, 1)
        self.graph = fig.add_subplot(gs[0, 0])
        plt.xlabel('Date')
        plt.ylabel('Consumption (kW)')
        plt.tight_layout()

    def draw(self):
        self.shouldScheduleDraw = True
        self.graph.relim()
        self.graph.autoscale_view(True, True, True)
        plt.draw()
        plt.legend(('actual', 'predicted'), loc=3)

    def step(self):
        self.counter += 1
        self.timestampStr, self.consumptionStr = csvReader.next()
        timestamp = datetime.datetime.strptime(self.timestampStr, "%m/%d/%y %H:%M")
        consumption = float(self.consumptionStr)
        result = self.model.run({
            "timestamp": timestamp,
            "kw_energy_consumption": consumption,
        })
        result.metrics = self.metricsManager.update(result)

        if self.counter % 100 == 0:
            print "Read %i lines..." % self.counter
            print ("After %i records, 1-step altMAPE=%f" % (
                self.counter,
                result.metrics["multiStepBestPredictions:multiStep:"
                               "errorMetric='altMAPE':steps=1:window=1000:"
                               "field=kw_energy_consumption"]))

        result = self.shifter.shift(result)
        prediction = result.inferences["multiStepBestPredictions"][1]

        if not self.linesInitialized:
            self.dates += deque([timestamp]*WINDOW)
            self.convertedDates += [date2num(date) for date in self.dates]

            addedLinesActual, = self.graph.plot(
                self.dates, self.actualValues, 'r'
            )
            self.actualLines = addedLinesActual

            predictedLinesActual, = self.graph.plot(
                self.dates, self.predictedValues, 'b'
            )
            self.predictedLines = predictedLinesActual
            self.graph.xaxis.set_major_formatter(DateFormatter("%H:%M"))
            self.linesInitialized = True

        self.dates.append(timestamp)
        self.convertedDates.append(date2num(timestamp))
        self.actualValues.append(consumption)
        self.predictedValues.append(prediction)

        self.actualLines.set_xdata(self.convertedDates)
        self.actualLines.set_ydata(self.actualValues)
        self.predictedLines.set_xdata(self.convertedDates)
        self.predictedLines.set_ydata(self.predictedValues)

        if self.shouldScheduleDraw:
            # If we're stepping the model really quickly, coalesce the redraws.
            self.shouldScheduleDraw = False
            t = threading.Timer(0.2, self.draw)
            t.start()

    def getInputDisplayText(self):
        return (["time", self.timestampStr],
                ["power consumption (kW)", self.consumptionStr])

if __name__ == '__main__':
    model = ModelFactory.create(MODEL_PARAMS)
    model.enableInference({"predictedField": "kw_energy_consumption"})

    inputPath = os.path.join(os.path.dirname(__file__),
                             "data/rec-center-hourly.csv")

    inputFile = open(inputPath, "rb")
    csvReader = csv.reader(inputFile)
    csvReader.next()
    csvReader.next()
    csvReader.next()

    runner.startRunner(HotGym(model, csvReader), 24601, useBackgroundThread=True)
    plt.show()
