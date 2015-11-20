from abc import ABCMeta, abstractmethod
from collections import deque

import numpy
from nupic.bindings.math import GetNTAReal

class VizModel(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        self.timestep = 0

        self.lastEventIds = {
            'didStep': 0,
        }
        self.listeners = {
            'didStep': {},
        }

    def addEventListener(self, event, fn):
        eventId = self.lastEventIds[event] + 1
        self.listeners[event][eventId] = fn
        self.lastEventIds[event] = eventId

    def removeEventListener(self, event, eventId):
        del self.listeners[event][eventId]

    def doStep(self):
        ret = self.step()
        if ret is not False:
            self.timestep += 1
            for fn in self.listeners['didStep'].values():
                fn()

        return ret

    @abstractmethod
    def step(self):
        """Run one input through the HTM.

        If there are no more inputs, return False.
        """

    @abstractmethod
    def query(self, getNetworkLayout=False, getBitStates=False, getProximalSynapses=False,
              proximalSynapsesQuery={}, getDistalSegments=False, distalSegmentsQuery={}):
        """
        """

    @abstractmethod
    def getInputDisplayText(self):
        """Return the most recent input as a dictionary or a list of key-value pairs.
        """

def proximalSynapsesFromSP(sp, targetBits=None, onlyConnectedSynapses=True, targetDepth=1):
    if not targetBits:
        targetBits = range(sp.getNumInputs())

    proximalSynapses = deque()
    permanence = numpy.zeros(sp.getNumInputs()).astype(GetNTAReal())
    for column in range(sp.getNumColumns()):
        sp.getPermanence(column, permanence)
        for inputBit in targetBits:
            if not onlyConnectedSynapses or permanence[inputBit] >= sp.getSynPermConnected():
                targetColumn = int(inputBit / targetDepth)
                syn = (column, targetColumn, permanence[inputBit])
                proximalSynapses.append(syn)

    return proximalSynapses

# TODO sourcePath is a hack
def distalSegmentsFromTM(tm, sourceColumns, targetBits, sourcePath):
    distalSegments = deque()
    for col in sourceColumns:
        for cell in range(tm.cellsPerColumn):
            for seg in tm.connections.segmentsForCell(col * tm.cellsPerColumn + cell):
                synapses = []
                nConnectedActive = 0
                nConnectedTotal = 0
                nDisconnectedActive = 0
                nDisconnectedTotal = 0
                for syn in tm.connections.synapsesForSegment(seg):
                    synapseData = tm.connections.dataForSynapse(syn)
                    isConnected = synapseData.permanence >= tm.connectedPermanence
                    # TODO not necessarily true
                    isActive = synapseData.presynapticCell in targetBits

                    if isConnected:
                        nConnectedTotal += 1
                    else:
                        nDisconnectedTotal += 1

                    if isActive:
                        if isConnected:
                            nConnectedActive += 1
                            presynapticCol = synapseData.presynapticCell / tm.cellsPerColumn
                            presynapticCellOffset = synapseData.presynapticCell % tm.cellsPerColumn
                            syn = (presynapticCol, presynapticCellOffset, synapseData.permanence)
                            synapses.append(syn)
                        else:
                            nDisconnectedActive += 1
                distalSegments.append({
                    "column": col,
                    "cell": cell,
                    "synapses": {
                        sourcePath: synapses,
                    },
                    "nConnectedActive": nConnectedActive,
                    "nConnectedTotal": nConnectedTotal,
                    "nDisconnectedActive": nDisconnectedActive,
                    "nDisconnectedTotal": nDisconnectedTotal,
                })

    return distalSegments

# TODO sourcePath is a hack
def distalSegmentsFromTP(tp, sourceColumns, targetBits, sourcePath):
    distalSegments = deque()
    for col in sourceColumns:
        for cell in range(tp.cellsPerColumn):
            for segIdx in range(tp.getNumSegmentsInCell(col, cell)):
                v = tp.getSegmentOnCell(col, cell, segIdx)
                segData = v[0]
                synapses = []
                nConnectedActive = 0
                nConnectedTotal = 0
                nDisconnectedActive = 0
                nDisconnectedTotal = 0
                for targetCol, targetCell, perm in v[1:]:
                    cellId = targetCol * tp.cellsPerColumn + targetCell
                    isConnected = perm >= tp.connectedPerm
                    # TODO not necessarily true
                    isActive = cellId in targetBits

                    if isConnected:
                        nConnectedTotal += 1
                    else:
                        nDisconnectedTotal += 1

                    if isActive:
                        if isConnected:
                            nConnectedActive += 1
                            syn = (targetCol, targetCell, perm)
                            synapses.append(syn)
                        else:
                            nDisconnectedActive += 1
                distalSegments.append({
                    "column": col,
                    "cell": cell,
                    "synapses": {
                        sourcePath: synapses,
                    },
                    "nConnectedActive": nConnectedActive,
                    "nConnectedTotal": nConnectedTotal,
                    "nDisconnectedActive": nDisconnectedActive,
                    "nDisconnectedTotal": nDisconnectedTotal,
                })

    return distalSegments

class CLAVizModel(VizModel):
    __metaclass__ = ABCMeta

    def __init__(self, model):
        super(CLAVizModel, self).__init__()
        self.model = model

    def query(self, getNetworkLayout=False, getBitStates=False, getProximalSynapses=False,
              proximalSynapsesQuery={}, getDistalSegments=False, distalSegmentsQuery={}):
        senses = {'concatenated': {}}
        regions = {'rgn-0': {'layer-3': {}}}

        spRegion = self.model._getSPRegion().getSelf()
        spOutput = spRegion._spatialPoolerOutput
        sp = spRegion._sfdr
        tp = self.model._getTPRegion().getSelf()._tfdr

        if getNetworkLayout:
            inputDimensions = sp.getInputDimensions()
            columnDimensions = sp.getColumnDimensions()
            # The python spatial pooler returns a numpy array.
            if hasattr(inputDimensions, 'tolist'):
                inputDimensions = inputDimensions.tolist()
            if hasattr(columnDimensions, 'tolist'):
                columnDimensions = columnDimensions.tolist()
            senses['concatenated']['dimensions'] = inputDimensions
            regions['rgn-0']['layer-3'].update({
                'dimensions': columnDimensions,
                'cellsPerColumn': tp.cellsPerColumn
            })

        if getBitStates:
            senses['concatenated'].update({
                'activeBits': set(spRegion._spatialPoolerInput.nonzero()[0].tolist()),
            })
            npPredictedCells = tp.getPredictedState().reshape(-1).nonzero()[0]
            regions['rgn-0']['layer-3'].update({
                "activeColumns": set(spOutput.nonzero()[0].tolist()),
                "activeCells": set(tp.getActiveState().nonzero()[0].tolist()),
                "predictedCells": set(npPredictedCells.tolist()),
                "predictedColumns": set(numpy.unique(npPredictedCells /
                                                     tp.cellsPerColumn).tolist()),
            })

        if getProximalSynapses:
            assert getBitStates

            onlyBits = None
            if proximalSynapsesQuery['onlyActive']:
                onlyBits = senses['concatenated']['activeBits']

            proximalSynapses = proximalSynapsesFromSP(sp, onlyBits,
                                                      proximalSynapsesQuery['onlyConnected'])

            regions['rgn-0']['layer-3'].update({
                'proximalSynapses': {
                    ('senses', 'concatenated'): proximalSynapses,
                }
            })

        if getDistalSegments:
            assert getBitStates

            columnsToCheck = (regions['rgn-0']['layer-3']['activeColumns'] |
                              distalSegmentsQuery['regions']['rgn-0']['layer-3']['additionalColumns'])
            onlyTargets = distalSegmentsQuery['regions']['rgn-0']['layer-3']['targets']

            distalSegments = None
            if hasattr(tp, "connections"):
                distalSegments = distalSegmentsFromTM(tp, columnsToCheck, onlyTargets,
                                                      ('regions', 'rgn-0', 'layer-3'))
            else:
                distalSegments = distalSegmentsFromTP(tp, columnsToCheck, onlyTargets,
                                                      ('regions', 'rgn-0', 'layer-3'))
            regions['rgn-0']['layer-3'].update({
                'distalSegments': distalSegments,
                "nDistalLearningThreshold": tp.minThreshold,
                "nDistalStimulusThreshold": tp.activationThreshold,
            })

        return {
            'senses': senses,
            'regions': regions,
        }
