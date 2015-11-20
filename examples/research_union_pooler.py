import datetime
import csv
import numpy
from collections import deque

from htmresearch.frameworks.union_temporal_pooling.union_temporal_pooler_experiment import (
    UnionTemporalPoolerExperiment)
from nupic.data.generators.pattern_machine import PatternMachine
from nupic.data.generators.sequence_machine import SequenceMachine

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import runner
from model import VizModel, proximalSynapsesFromSP, distalSegmentsFromTM
from swarmed_model_params import MODEL_PARAMS

class UnionPoolingExperimentVizModel(VizModel):
    def __init__(self, experiment, patterns, labels):
        super(UnionPoolingExperimentVizModel, self).__init__()
        self.experiment = experiment
        self.patterns = patterns
        self.labels = labels
        self.lastInputIndex = -1

    def step(self):
        self.lastInputIndex += 1
        pattern = self.patterns[self.lastInputIndex]
        label = self.labels[self.lastInputIndex]

        if pattern:
            self.experiment.runNetworkOnPattern(pattern,
                                                tmLearn=True,
                                                upLearn=True,
                                                sequenceLabel=label)
        else:
            self.experiment.tm.reset()
            self.experiment.up.reset()

    def getInputDisplayText(self):
        if self.lastInputIndex >= 0:
            return [
                ['input', self.labels[self.lastInputIndex],]
            ]
        else:
            return []

    def query(self, getNetworkLayout=False, getBitStates=False, getProximalSynapses=False,
              proximalSynapsesQuery={}, getDistalSegments=False, distalSegmentsQuery={}):
        senses = {
            'input': {}
        }
        regions = {
            'tm': {'layer': {}},
            'up': {'layer': {}},
        }

        tm = self.experiment.tm
        up = self.experiment.up

        if getNetworkLayout:
            senses['input']['dimensions'] = tm.columnDimensions

            regions['tm']['layer'].update({
                'cellsPerColumn': tm.cellsPerColumn,
                'dimensions': tm.columnDimensions,
            })

            regions['up']['layer'].update({
                'cellsPerColumn': 1,
                'dimensions': up.getColumnDimensions().tolist()
            })

        if getBitStates:
            activeBits = set()
            if self.lastInputIndex >= 0:
                pattern = self.patterns[self.lastInputIndex]
                if pattern:
                    activeBits = set(pattern)

            senses['input'].update({
                'activeBits': activeBits,
            })

            predictiveCells = set(tm.predictiveCells)
            predictiveColumns = set(cell / tm.cellsPerColumn for cell in predictiveCells)
            regions['tm']['layer'].update({
                'activeColumns': activeBits,
                'activeCells': set(tm.activeCells),
                'predictedCells': set(predictiveCells),
                'predictedColumns': predictiveColumns,
            })

            activeColumns = set(up.getUnionSDR().tolist())
            regions['up']['layer'].update({
                'activeColumns': activeColumns,
                'activeCells': activeColumns,
                'predictedCells': set(),
                'predictedColumns': set(),
            })

        if getProximalSynapses:
            assert getBitStates

            # Pseudo-synapses
            tmSynapses = deque((column, column, 1)
                               for column in range(tm.numberOfColumns()))
            regions['tm']['layer'].update({
                'proximalSynapses': {
                    ('senses', 'input'): tmSynapses,
                },
            })

            onlyTmBits = None
            if proximalSynapsesQuery['onlyActive']:
                onlyTmBits = regions['tm']['layer']['activeCells']

            upSynapses = proximalSynapsesFromSP(up, onlyTmBits,
                                                proximalSynapsesQuery['onlyConnected'],
                                                targetDepth=tm.cellsPerColumn)

            regions['up']['layer'].update({
                'proximalSynapses': {
                    ('regions', 'tm', 'layer'): upSynapses,
                },
            })

        if getDistalSegments:
            assert getBitStates

            columnsToCheck = (regions['tm']['layer']['activeColumns'] |
                              distalSegmentsQuery['regions']['tm']['layer']['additionalColumns'])
            onlyTargets = distalSegmentsQuery['regions']['tm']['layer']['targets']

            distalSegments = distalSegmentsFromTM(tm, columnsToCheck, onlyTargets,
                                                  sourcePath=('regions', 'tm', 'layer'))

            regions['tm']['layer'].update({
                'distalSegments': distalSegments,
                "nDistalLearningThreshold": tm.minThreshold,
                "nDistalStimulusThreshold": tm.activationThreshold,
            })

        return {
            'senses': senses,
            'regions': regions,
        }


if __name__ == '__main__':
    experiment = UnionTemporalPoolerExperiment()

    # Dimensionality of sequence patterns
    patternDimensionality = 1024

    # Cardinality (ON / true bits) of sequence patterns
    patternCardinality = 50

    # Length of sequences shown to network
    sequenceLength = 50

    # Number of sequences used. Sequences may share common elements.
    numberOfSequences = 1

    # Generate a sequence list and an associated labeled list (both containing a
    # set of sequences separated by None)
    print "\nGenerating sequences..."
    patternAlphabetSize = sequenceLength * numberOfSequences
    patternMachine = PatternMachine(patternDimensionality, patternCardinality,
                                    patternAlphabetSize)
    sequenceMachine = SequenceMachine(patternMachine)

    numbers = sequenceMachine.generateNumbers(numberOfSequences, sequenceLength)
    generatedSequences = sequenceMachine.generateFromNumbers(numbers)

    inputs = list(generatedSequences) * 100
    labels = list(numbers) * 100

    # TODO: show higher-level sequence *and* current value in display text.
    vizModel = UnionPoolingExperimentVizModel(experiment, inputs, labels)
    runner.startRunner(vizModel, 24601)
