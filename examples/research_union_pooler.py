import datetime
import csv
import numpy
from collections import deque

from htmresearch.frameworks.union_temporal_pooling.union_temporal_pooler_experiment import (
    UnionTemporalPoolerExperiment)
from nupic.data.generators.pattern_machine import PatternMachine
from nupic.data.generators.sequence_machine import SequenceMachine
from nupic.bindings.math import GetNTAReal # TODO I should be able to
                                           # refactor and not need
                                           # this here.

import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import runner
from model import VizModel
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
        cellsPerColumn = tm.cellsPerColumn

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
                    activeBits = pattern

            senses['input'].update({
                'activeBits': activeBits,
            })

            predictiveCells = tm.predictiveCells
            predictiveColumns = set(cell / cellsPerColumn for cell in predictiveCells)
            regions['tm']['layer'].update({
                'activeColumns': activeBits,
                'activeCells': tm.activeCells,
                'predictedCells': predictiveCells,
                'predictedColumns': predictiveColumns,
            })

            activeColumns = up.getUnionSDR().tolist()
            regions['up']['layer'].update({
                'activeColumns': activeColumns,
                'activeCells': activeColumns,
                'predictedCells': [],
                'predictedColumns': [],
            })

        if getProximalSynapses:
            assert getBitStates

            onlyTmBits = None
            if proximalSynapsesQuery['onlyActive']:
                onlyTmBits = regions['tm']['layer']['activeCells']
            else:
                onlyTmBits = tm.numberOfColumns()

            # Pseudo-synapses
            tmSyns = deque((column, column, 1)
                           for column in range(tm.numberOfColumns()))
            regions['tm']['layer'].update({
                'proximalSynapses': {
                    ('senses', 'input'): tmSyns,
                },
            })

            upSyns = deque()
            permanence = numpy.zeros(up.getNumInputs()).astype(GetNTAReal())
            for column in range(up.getNumColumns()):
                up.getPermanence(column, permanence)
                for inputBit in onlyTmBits:
                    if not proximalSynapsesQuery['onlyConnected'] or \
                       permanence[inputBit] >= up.getSynPermConnected():
                        inputColumn = int(inputBit / cellsPerColumn)
                        syn = (column, inputColumn, float(permanence[inputBit]))
                        upSyns.append(syn)

            regions['up']['layer'].update({
                'proximalSynapses': {
                    ('regions', 'tm', 'layer'): upSyns,
                },
            })

        if getDistalSegments:
            assert getBitStates

            distalSegments = deque()

            columnsToCheck = (regions['tm']['layer']['activeColumns'] |
                              distalSegmentsQuery['regions']['tm']['layer']['additionalColumns'])
            onlyTargets = distalSegmentsQuery['regions']['tm']['layer']['targets']

            for col in columnsToCheck:
                for cell in range(cellsPerColumn):
                    for seg in tm.connections.segmentsForCell(col * cellsPerColumn + cell):
                        synapses = []
                        nConnectedActive = 0
                        nConnectedTotal = 0
                        nDisconnectedActive = 0
                        nDisconnectedTotal = 0
                        for syn in tm.connections.synapsesForSegment(seg):
                            synapseData = tm.connections.dataForSynapse(syn)
                            isConnected = synapseData.permanence >= tm.connectedPermanence
                            isActive = synapseData.presynapticCell in onlyTargets

                            if isConnected:
                                nConnectedTotal += 1
                            else:
                                nDisconnectedTotal += 1

                            if isActive:
                                if isConnected:
                                    nConnectedActive += 1
                                    presynapticCol = synapseData.presynapticCell / cellsPerColumn
                                    presynapticCellOffset = synapseData.presynapticCell % cellsPerColumn
                                    syn = (presynapticCol, presynapticCellOffset, synapseData.permanence)
                                    synapses.append(syn)
                                else:
                                    nDisconnectedActive += 1
                        distalSegments.append({
                            "column": col,
                            "cell": cell,
                            "synapses": {
                                ('regions', 'tm', 'layer'): synapses,
                            },
                            "nConnectedActive": nConnectedActive,
                            "nConnectedTotal": nConnectedTotal,
                            "nDisconnectedActive": nDisconnectedActive,
                            "nDisconnectedTotal": nDisconnectedTotal,
                        })

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
