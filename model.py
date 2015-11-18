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
    def getInputDisplayText(self):
        """Return the most recent input as a dictionary or a list of key-value pairs.
        """

    # Is this right? Maybe I should have a VizSense, VizRegion,
    # VizLayer, and the journal should call into their APIs?  Whatever
    # happens, I won't go any lower than layers. I offer a "I will not
    # create a VizSegment class" guarantee.
    @abstractmethod
    def getNetworkLayout(self):
        """
        """

    # TODO do this by layer
    @abstractmethod
    def getCellsPerColumn(self):
        """
        """

    # TODO do this by layer
    @abstractmethod
    def getBitStates(self):
        """
        """

    # TODO do this by layer
    @abstractmethod
    def getProximalSynapses(self, onlyBits, onlyConnected=True):
        """
        """

    @abstractmethod
    def getDistalSegments(self, columnsToCheck, onlyTargets, onlyConnected=True):
        """
        """


class OpfVizModel(VizModel):
    __metaclass__ = ABCMeta

    def __init__(self, model):
        super(OpfVizModel, self).__init__()
        self.model = model

    def getNetworkLayout(self):

        sp = self.model._getSPRegion().getSelf()._sfdr
        inputDimensions = sp.getInputDimensions()
        columnDimensions = sp.getColumnDimensions()
        # The python spatial pooler returns a numpy array.
        if hasattr(inputDimensions, 'tolist'):
            inputDimensions = inputDimensions.tolist()
        if hasattr(columnDimensions, 'tolist'):
            columnDimensions = columnDimensions.tolist()

        return {
            'senses': {
                'concatenated': {
                    'dimensions': inputDimensions,
                },
            },
            'regions': {
                'rgn-0': {
                    'layer-3': {
                        'dimensions': columnDimensions,
                    },
                },
            },
        }


    def getCellsPerColumn(self):
        return self.model._getTPRegion().getSelf()._tfdr.cellsPerColumn

    # TODO do this by layer
    def getBitStates(self):
        spRegion = self.model._getSPRegion().getSelf()
        spOutput = spRegion._spatialPoolerOutput
        tp = self.model._getTPRegion().getSelf()._tfdr
        npPredictedCells = tp.getPredictedState().reshape(-1).nonzero()[0]

        return {
            "activeBits": spRegion._spatialPoolerInput.nonzero()[0].tolist(),
            "activeColumns": spOutput.nonzero()[0].tolist(),
            "activeCells": tp.getActiveState().nonzero()[0].tolist(),
            "nDistalLearningThreshold": tp.minThreshold,
            "nDistalStimulusThreshold": tp.activationThreshold,
            "predictedCells": npPredictedCells.tolist(),
            "predictedColumns": numpy.unique(npPredictedCells / tp.cellsPerColumn).tolist(),
        }

    # TODO do this by layer
    def getProximalSynapses(self, onlyBits, onlyConnected=True):
        proximalSynapses = deque()
        spRegion = self.model._getSPRegion().getSelf()
        sp = spRegion._sfdr
        tpRegion = self.model._getTPRegion()
        tp = tpRegion.getSelf()._tfdr

        numColumns = sp.getNumColumns()
        numInputs = sp.getNumInputs()
        permanence = numpy.zeros(numInputs).astype(GetNTAReal())
        for column in range(numColumns):
            sp.getPermanence(column, permanence)
            for inputBit in onlyBits:
                if not onlyConnected or permanence[inputBit] >= spRegion.synPermConnected:
                    syn = (column, int(inputBit), permanence[inputBit].tolist())
                    proximalSynapses.append(syn)

        return proximalSynapses

    # TODO do this by layer
    def getDistalSegments(self, columnsToCheck, onlyTargets, onlyConnected=True):
        spRegion = self.model._getSPRegion().getSelf()
        sp = spRegion._sfdr
        tp = self.model._getTPRegion().getSelf()._tfdr

        distalSegments = deque()

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

        return distalSegments
