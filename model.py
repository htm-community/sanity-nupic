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
        self.step()
        self.timestep += 1
        for fn in self.listeners['didStep'].values():
            fn()

    @abstractmethod
    def step(self):
        """Run one input through the HTM.
        """

    @abstractmethod
    def query(self, networkLayout=False, bitStates=False, proximalSynapses=False,
              proximalSynapsesQuery={}, distalSegments=False, distalSegmentsQuery={}):
        """
        """

    @abstractmethod
    def getInputDisplayText(self):
        """Return the most recent input as a dictionary or a list of key-value pairs.
        """


class CLAVizModel(VizModel):
    __metaclass__ = ABCMeta

    def __init__(self, model):
        super(CLAVizModel, self).__init__()
        self.model = model

    def query(self, networkLayout=False, bitStates=False, proximalSynapses=False,
              proximalSynapsesQuery={}, distalSegments=False, distalSegmentsQuery={}):
        senses = {'concatenated': {}}
        regions = {'rgn-0': {'layer-3': {}}}

        spRegion = self.model._getSPRegion().getSelf()
        spOutput = spRegion._spatialPoolerOutput
        sp = spRegion._sfdr
        tp = self.model._getTPRegion().getSelf()._tfdr

        if networkLayout:
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

        if bitStates:
            senses['concatenated'].update({
                'activeBits': spRegion._spatialPoolerInput.nonzero()[0].tolist()
            })
            npPredictedCells = tp.getPredictedState().reshape(-1).nonzero()[0]
            regions['rgn-0']['layer-3'].update({
                "activeColumns": spOutput.nonzero()[0].tolist(),
                "activeCells": tp.getActiveState().nonzero()[0].tolist(),
                "predictedCells": npPredictedCells.tolist(),
                "predictedColumns": numpy.unique(npPredictedCells / tp.cellsPerColumn).tolist(),
            })

        if proximalSynapses:
            assert bitStates

            proximalSynapses = deque()

            onlyBits = None
            if proximalSynapsesQuery['onlyActive']:
                onlyBits = senses['concatenated']['activeBits']
            else:
                onlyBits = sp.getNumInputs()

            permanence = numpy.zeros(sp.getNumInputs()).astype(GetNTAReal())
            for column in range(sp.getNumColumns()):
                sp.getPermanence(column, permanence)
                for inputBit in onlyBits:
                    if not proximalSynapsesQuery['onlyConnected'] or \
                       permanence[inputBit] >= spRegion.synPermConnected:
                        syn = (column, int(inputBit), permanence[inputBit].tolist())
                        proximalSynapses.append(syn)

            regions['rgn-0']['layer-3'].update({
                'proximalSynapses': {
                    ('senses', 'concatenated'): proximalSynapses,
                }
            })

        if distalSegments:
            assert bitStates

            distalSegments = deque()

            columnsToCheck = (regions['rgn-0']['layer-3']['activeColumns'] +
                              distalSegmentsQuery['regions']['rgn-0']['layer-3']['additionalColumns'])
            onlyTargets = distalSegmentsQuery['regions']['rgn-0']['layer-3']['targets']

            for col in columnsToCheck:
                for cell in range(tp.cellsPerColumn):
                    if hasattr(tp, "connections"):
                        # temporal_memory.py
                        for seg in tp.connections.segmentsForCell(col * tp.cellsPerColumn + cell):
                            synapses = []
                            nConnectedActive = 0
                            nConnectedTotal = 0
                            nDisconnectedActive = 0
                            nDisconnectedTotal = 0
                            for syn in tp.connections.synapsesForSegment(seg):
                                synapseData = tp.connections.dataForSynapse(syn)
                                isConnected = synapseData.permanence >= tp.connectedPermanence
                                isActive = synapseData.presynapticCell in onlyTargets

                                if isConnected:
                                    nConnectedTotal += 1
                                else:
                                    nDisconnectedTotal += 1

                                if isActive:
                                    if isConnected:
                                        nConnectedActive += 1
                                        presynapticCol = synapseData.presynapticCell / tp.cellsPerColumn
                                        presynapticCellOffset = synapseData.presynapticCell % tp.cellsPerColumn
                                        syn = (presynapticCol, presynapticCellOffset, synapseData.permanence)
                                        synapses.append(syn)
                                    else:
                                        nDisconnectedActive += 1
                            distalSegments.append({
                                "column": col,
                                "cell": cell,
                                "synapses": synapses,
                                "nConnectedActive": nConnectedActive,
                                "nConnectedTotal": nConnectedTotal,
                                "nDisconnectedActive": nDisconnectedActive,
                                "nDisconnectedTotal": nDisconnectedTotal,
                            })
                    else:
                        # tm.py
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
                                isActive = cellId in onlyTargets

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
                                "synapses": synapses,
                                "nConnectedActive": nConnectedActive,
                                "nConnectedTotal": nConnectedTotal,
                                "nDisconnectedActive": nDisconnectedActive,
                                "nDisconnectedTotal": nDisconnectedTotal,
                            })

            regions['rgn-0']['layer-3'].update({
                'distalSegments': distalSegments,
                "nDistalLearningThreshold": tp.minThreshold,
                "nDistalStimulusThreshold": tp.activationThreshold,
            })

        return {
            'senses': senses,
            'regions': regions,
        }
