import datetime
import csv
import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import runner
from model import CLAVizModel
from swarmed_model_params import MODEL_PARAMS

from nupic.frameworks.opf.metrics import MetricSpec
from nupic.frameworks.opf.modelfactory import ModelFactory
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

class HotGym(CLAVizModel):
    def __init__(self, model, inputs):
        super(HotGym, self).__init__(model)
        self.model = model
        self.inputs = inputs
        self.metricsManager = MetricsManager(_METRIC_SPECS, model.getFieldInfo(),
                                             model.getInferenceType())
        self.counter = 0
        self.timestampStr = ""
        self.consumptionStr = ""

    def step(self):
        self.counter += 1
        self.timestampStr, self.consumptionStr = self.inputs.next()
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

    runner.startRunner(HotGym(model, csvReader), 24601)
