import datetime

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import runner

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

    runner.startRunner(model, step, 24601)
