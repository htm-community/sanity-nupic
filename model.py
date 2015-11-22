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
    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSynapses=False, proximalSynapsesQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        """
        """

    @abstractmethod
    def getInputDisplayText(self):
        """Return the most recent input as a dictionary or a list of key-value pairs.
        """

def proximalSynapsesFromSP(sp, activeBits, onlyActiveSynapses,
                           onlyConnectedSynapses, targetDepth=1):
    activeSyns = deque()
    inactiveSyns = deque()
    disconnectedSyns = deque()
    permanence = numpy.zeros(sp.getNumInputs()).astype(GetNTAReal())
    synPermConnected = sp.getSynPermConnected()
    for column in range(sp.getNumColumns()):
        sp.getPermanence(column, permanence)
        # TODO don't just scan activeBits
        for inputBit in activeBits:
            isActive = True
            isConnected = permanence[inputBit] >= synPermConnected
            if isConnected:
                targetColumn = int(inputBit / targetDepth)
                syn = (column, targetColumn, permanence[inputBit])
                activeSyns.append(syn)

    return {
        'active': activeSyns,
        'inactive-syn': inactiveSyns,
        'disconnected': disconnectedSyns,
    }

# TODO sourcePath is a hack
def segmentsFromConnections(connections, tm, sourceColumns,
                            targetBits, sourcePath, sourceCellsPerColumn,
                            sourceCellOffset=0):

    segments = deque()
    for col in sourceColumns:
        for cell in range(tm.cellsPerColumn):
            for seg in connections.segmentsForCell(col * tm.cellsPerColumn + cell):
                synapses = []
                nConnectedActive = 0
                nConnectedTotal = 0
                nDisconnectedActive = 0
                nDisconnectedTotal = 0
                for syn in connections.synapsesForSegment(seg):
                    synapseData = connections.dataForSynapse(syn)

                    # GeneralTemporalMemory describes apical targets
                    # in terms of its own cell indices, not in terms
                    # of a remote region.
                    presynapticCell = synapseData.presynapticCell + sourceCellOffset

                    isConnected = synapseData.permanence >= tm.connectedPermanence
                    # TODO not necessarily true
                    isActive = presynapticCell in targetBits

                    if isConnected:
                        nConnectedTotal += 1
                    else:
                        nDisconnectedTotal += 1

                    if isActive:
                        if isConnected:
                            nConnectedActive += 1
                            presynapticCol = presynapticCell / sourceCellsPerColumn
                            presynapticCellOffset = presynapticCell % sourceCellsPerColumn
                            syn = (presynapticCol, presynapticCellOffset, synapseData.permanence)
                            synapses.append(syn)
                        else:
                            nDisconnectedActive += 1
                segments.append({
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

    return segments

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

    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSynapses=False, proximalSynapsesQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        senses = {'concatenated': {}}
        regions = {'rgn-0': {'layer-3': {}}}

        spRegion = self.model._getSPRegion().getSelf()
        spOutput = spRegion._spatialPoolerOutput
        sp = spRegion._sfdr
        tp = self.model._getTPRegion().getSelf()._tfdr

        if getNetworkLayout:
            senses['concatenated'].update({
                'dimensions': sp.getInputDimensions(),
                'ordinal': 0,
            })
            regions['rgn-0']['layer-3'].update({
                'dimensions': sp.getColumnDimensions(),
                'cellsPerColumn': tp.cellsPerColumn,
                'ordinal': 1,
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
            proximalSynapses = proximalSynapsesFromSP(sp,
                                                      senses['concatenated']['activeBits'],
                                                      proximalSynapsesQuery['onlyActive'],
                                                      proximalSynapsesQuery['onlyConnected'])

            regions['rgn-0']['layer-3'].update({
                'proximalSynapses': {
                    ('senses', 'concatenated'): proximalSynapses,
                }
            })

        if getDistalSegments:
            assert getBitStates
            try:
                prevState = bitHistory.next()
                columnsToCheck = (regions['rgn-0']['layer-3']['activeColumns'] |
                                  prevState['regions']['rgn-0']['layer-3']['predictedColumns'])
                onlySources = prevState['regions']['rgn-0']['layer-3']['activeCells']
                if hasattr(tp, "connections"):
                    distalSegments = segmentsFromConnections(tp.connections, tp,
                                                             columnsToCheck,
                                                             onlySources,
                                                             ('regions',
                                                              'rgn-0',
                                                              'layer-3'),
                                                             tp.cellsPerColumn)
                else:
                    distalSegments = distalSegmentsFromTP(tp, columnsToCheck,
                                                          onlySources,
                                                          ('regions', 'rgn-0',
                                                           'layer-3'))
                regions['rgn-0']['layer-3'].update({
                    'distalSegments': distalSegments,
                    "nDistalLearningThreshold": tp.minThreshold,
                    "nDistalStimulusThreshold": tp.activationThreshold,
                })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'regions': regions,
        }
