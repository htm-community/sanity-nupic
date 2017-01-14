import csv
import datetime
import os

import numpy as np

from nupic.bindings.algorithms import SpatialPooler, TemporalMemory
from nupic.encoders.date import DateEncoder
from nupic.encoders.random_distributed_scalar import (
  RandomDistributedScalarEncoder)

import htmsanity.nupic.runner as sanity

def go():
  valueEncoder = RandomDistributedScalarEncoder(resolution=0.88, seed=42)
  timestampEncoder = DateEncoder(timeOfDay=(21, 9.49, ))

  inputWidth = timestampEncoder.getWidth() + valueEncoder.getWidth()

  sp = SpatialPooler(**{
    "globalInhibition": True,
    "columnDimensions": [2048],
    "inputDimensions": [inputWidth],
    "potentialRadius": inputWidth,
    "numActiveColumnsPerInhArea": 40,
    "seed": 1956,
    "potentialPct": 0.8,
    "boostStrength": 0.0,
    "synPermActiveInc": 0.003,
    "synPermConnected": 0.2,
    "synPermInactiveDec": 0.0005,
  })

  tm = TemporalMemory(**{
    "activationThreshold": 20,
    "cellsPerColumn": 32,
    "columnDimensions": (2048,),
    "initialPermanence": 0.24,
    "maxSegmentsPerCell": 128,
    "maxSynapsesPerSegment": 128,
    "minThreshold": 13,
    "maxNewSynapseCount": 31,
    "permanenceDecrement": 0.008,
    "permanenceIncrement": 0.04,
    "seed": 1961,
  })


  inputPath = os.path.join(os.path.dirname(__file__),
                           "data/rec-center-hourly.csv")
  inputFile = open(inputPath, "rb")
  csvReader = csv.reader(inputFile)
  csvReader.next()
  csvReader.next()
  csvReader.next()

  encodedValue = np.zeros(valueEncoder.getWidth(), dtype=np.uint32)
  encodedTimestamp = np.zeros(timestampEncoder.getWidth(), dtype=np.uint32)
  spOutput = np.zeros(2048, dtype=np.float32)


  sanityInstance = sanity.SPTMInstance(sp, tm)


  for timestampStr, consumptionStr in csvReader:

    sanityInstance.waitForUserContinue()

    timestamp = datetime.datetime.strptime(timestampStr, "%m/%d/%y %H:%M")
    consumption = float(consumptionStr)

    timestampEncoder.encodeIntoArray(timestamp, encodedTimestamp)
    valueEncoder.encodeIntoArray(consumption, encodedValue)

    sensoryInput = np.concatenate((encodedTimestamp, encodedValue,))
    sp.compute(sensoryInput, True, spOutput)

    activeColumns = np.flatnonzero(spOutput)
    predictedCells = tm.getPredictiveCells()
    tm.compute(activeColumns)

    activeInputBits = np.flatnonzero(sensoryInput)
    displayText = {"timestamp": timestampStr, "consumption": consumptionStr}

    sanityInstance.appendTimestep(activeInputBits, activeColumns, predictedCells,
                                  displayText)


if __name__ == '__main__':
  go()
