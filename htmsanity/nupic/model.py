from abc import ABCMeta, abstractmethod
from collections import deque, Mapping

import numpy as np
from nupic.bindings.math import GetNTAReal

class SanityModel(object):
    """
    Abstract base class. A SanityModel serves two functions:
     - Describe an HTM model in terms of layers and senses
     - Step the model
    """
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
            self.onStepped()

        return ret

    def onStepped(self):
        self.timestep += 1
        for fn in self.listeners['didStep'].values():
            fn()

    @abstractmethod
    def step(self):
        """
        Run one input through the HTM.

        Returns
        -------
        bool
          If there are no more inputs, return False.
        """

    @abstractmethod
    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        """
        Describe the model's state in terms of layers and senses.

        Parameters
        ----------
        bitHistory : iterator
          Provides access to getBitStates return values for previous timesteps.
          The first call to bitHistory.next() returns t - 1, the second t - 2, etc.
          This iterator is only valid for the duration of this query.
        getNetworkLayout : bool
          Whether to fetch this set of values. See the annotated return example.
        getProximalSegments : bool
          Whether to fetch this set of values. See the annotated return example.
        getDistalSegments : bool
          Whether to fetch this set of values. See the annotated return example.
        getApicalSegments : bool
          Whether to fetch this set of values. See the annotated return example.
        proximalSegmentsQuery : dict
          Details for the getProximalSegments.
          Example value:
            {
                'onlyActiveSynapses': True,
                'onlyConnectedSynapses': True,
            }
        distalSegmentsQuery : dict
          Details for the getDistalSegments.
          Example value:
            {
                'onlyActiveSynapses': True,
                'onlyConnectedSynapses': True,
                # Open to interpretation. Recommended: active and predicted columns.
                'onlyNoteworthyColumns': True,
            }
        apicalSegmentsQuery : dict
          Details for the getApicalSegments.
          Example value:
            {
                'onlyActiveSynapses': True,
                'onlyConnectedSynapses': True,
                # Open to interpretation. Recommended: active and predicted columns.
                'onlyNoteworthyColumns': True,
            }

        Returns
        -------
        dict
          The result of the query. See the annotated example.

        Here's a sample return value, annotated with the query parameter that
        summons each part:

        {
            'senses': {
                'mySense1': {
                    # getNetworkLayout
                    'ordinal': 0, # Display order
                    'dimensions': (200,),

                    # getBitStates
                    'activeBits': set([159, 160, 161,])
                }
            }
            'layers': {
                'myLayer3': {
                    # getNetworkLayout
                    'ordinal': 1, # Display order
                    'cellsPerColumn': 32,
                    'dimensions': (20,),

                    # getBitStates
                    'activeCells': set([0, 1, 2,]),
                    'activeColumns': set([0, 4, 5, 6, 9, 10,]),
                    'predictedColumns': set([])
                    'predictedCells': set([]),

                    # getProximalSegments
                    'proximalSegments': {
                        # Same format as distalSegments
                    },

                    # getApicalSegments
                    'nDistalStimulusThreshold': 13,
                    'nDistalLearningThreshold': 9,
                    'apicalSegments': [
                        # Same format as distalSegments
                    ],

                    # getDistalSegments
                    'nDistalStimulusThreshold': 13,
                    'nDistalLearningThreshold': 9,
                    'distalSegments': {
                        # Column
                        0: {
                            # Cell
                            9: [{
                                'nDisconnectedActive': 0,
                                'nDisconnectedTotal': 0,
                                'nConnectedActive': 6,
                                'nConnectedTotal': 10
                                'synapses': {
                                    # Path to presynaptic layer / sense
                                    ('layers', 'myLayer3'): [
                                        'active': [
                                            # Tuple:
                                            # - Presynaptic bit
                                            # - Permanence
                                            (0, 0.7100000381469727),
                                            (4, 0.7100000381469727),
                                        ],
                                        'disconnected': [],
                                        'inactive': [],
                                    ]
                                },
                            },
                            {
                                'nDisconnectedTotal': 10,
                                'nDisconnectedActive': 7,
                                'nConnectedActive': 0,
                                'nConnectedTotal': 0
                                'synapses': {
                                    ('layers', 'myLayer3'): []
                                },
                            },],
                        },
                    },
                }
            },
        }
        """

    @abstractmethod
    def getInputDisplayText(self):
        """
        Get the most recent input as a collection of key value pairs.
        The keys and values will be displayed as text.

        Returns
        -------
        dict or sequence
          Key value pairs. Use a sequential collection to control the display order.

        Example:
          [
              ("stage", "Train (trial 9 of 10)"),
              ("input", "squealed"),
          ]
        """

def proximalSegmentsFromSP(sp, activeBits, onlyActiveSynapses, onlyConnectedSynapses, sourcePath):
    segsByColCell = {}
    synPermConnected = sp.getSynPermConnected()
    synapsePotentials = np.zeros(sp.getNumInputs()).astype('uint32')
    synapsePermanences = np.zeros(sp.getNumInputs()).astype(GetNTAReal())
    activeMask = np.zeros(sp.getNumInputs(), dtype=bool)
    activeMask[list(activeBits)] = True
    for column in range(sp.getNumColumns()):
        segsByColCell[column] = {}

        sp.getPotential(column, synapsePotentials)
        potentialMask = synapsePotentials == 1

        sp.getPermanence(column, synapsePermanences)
        connectedMask = synapsePermanences >= synPermConnected

        activeConnectedMask = activeMask & potentialMask & connectedMask
        activeSyns = [(inputBit, synapsePermanences[inputBit])
                      for inputBit in activeConnectedMask.nonzero()[0]]

        inactiveSyns = []
        if not onlyActiveSynapses:
            inactiveConnectedMask = ~activeMask & potentialMask & connectedMask
            inactiveSyns = [(inputBit, synapsePermanences[inputBit])
                            for inputBit in inactiveConnectedMask.nonzero()[0]]

        disconnectedSyns = []
        if not onlyConnectedSynapses:
            disconnectedMask = potentialMask & ~connectedMask
            if onlyActiveSynapses:
                disconnectedMask = disconnectedMask & activeMask
            inactiveConnectedMask = ~activeMask & potentialMask & connectedMask
            disconnectedSyns = [(inputBit, synapsePermanences[inputBit])
                                for inputBit in inactiveConnectedMask.nonzero()[0]]

        segsByColCell[column][-1] = [{
            'synapses': {
                sourcePath: {
                    'active': activeSyns,
                    'inactive': inactiveSyns,
                    'disconnectedSyns': disconnectedSyns,
                }
            },
        }]

    return segsByColCell

# TODO sourcePath is a hack
def segmentsFromConnections(connections, tm, onlyColumns, activeBits,
                            sourcePath, onlyActiveSynapses,
                            onlyConnectedSynapses, sourceCellOffset=0):
    segsByColCell = {}
    for col in onlyColumns:
        segsByColCell[col] = {}
        for cell in range(tm.getCellsPerColumn()):
            segs = []
            for seg in connections.segmentsForCell(col * tm.getCellsPerColumn() + cell):
                activeSynapses = deque()
                inactiveSynapses = deque()
                disconnectedSynapses = deque()
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

                    isConnected = synapseData.permanence >= tm.getConnectedPermanence()
                    isActive = presynapticCell in activeBits

                    if isConnected:
                        nConnectedTotal += 1
                    else:
                        nDisconnectedTotal += 1

                    if isActive:
                        if isConnected:
                            nConnectedActive += 1
                        else:
                            nDisconnectedActive += 1

                    synapseList = None
                    if isActive and isConnected:
                        synapseList = activeSynapses
                    elif isConnected:
                        if not onlyActiveSynapses:
                            synapseList = inactiveSynapses
                    else:
                        if not onlyConnectedSynapses:
                            synapseList = disconnectedSynapses

                    if synapseList is not None:
                        syn = (presynapticCell, synapseData.permanence)
                        synapseList.append(syn)
                segs.append({
                    "synapses": {
                        sourcePath: {
                            'active': activeSynapses,
                            'inactive-syn': inactiveSynapses,
                            'disconnected': disconnectedSynapses,
                        },
                    },
                    "nConnectedActive": nConnectedActive,
                    "nConnectedTotal": nConnectedTotal,
                    "nDisconnectedActive": nDisconnectedActive,
                    "nDisconnectedTotal": nDisconnectedTotal,
                })
            segsByColCell[col][cell] = segs

    return segsByColCell


def segmentsFromConnections2(connections, tm, onlyColumns, activeBits,
                             onlyActiveSynapses, onlyConnectedSynapses, inputsAndWidths):
    segsByColCell = {}
    for col in onlyColumns:
        segsByColCell[col] = {}
        for cell in range(tm.getCellsPerColumn()):
            segs = []
            for seg in connections.segmentsForCell(col * tm.getCellsPerColumn() + cell):
                nConnectedActive = 0
                nConnectedTotal = 0
                nDisconnectedActive = 0
                nDisconnectedTotal = 0
                synapsesBySource = {}

                synapses = [connections.dataForSynapse(syn)
                            for syn in connections.synapsesForSegment(seg)]
                synapses = sorted(synapses, key=lambda a: a.presynapticCell)

                offset = 0
                synapseIdx = 0
                for sourcePath, width in inputsAndWidths:
                    activeSynapses = deque()
                    inactiveSynapses = deque()
                    disconnectedSynapses = deque()
                    while (synapseIdx < len(synapses) and
                           synapses[synapseIdx].presynapticCell < offset + width):
                        synapseData = synapses[synapseIdx]

                        isConnected = synapseData.permanence >= tm.getConnectedPermanence()
                        isActive = synapseData.presynapticCell in activeBits

                        if isConnected:
                            nConnectedTotal += 1
                        else:
                            nDisconnectedTotal += 1

                        if isActive:
                            if isConnected:
                                nConnectedActive += 1
                            else:
                                nDisconnectedActive += 1

                        synapseList = None
                        if isActive and isConnected:
                            synapseList = activeSynapses
                        elif isConnected:
                            if not onlyActiveSynapses:
                                synapseList = inactiveSynapses
                        else:
                            if not onlyConnectedSynapses:
                                synapseList = disconnectedSynapses

                        if synapseList is not None:
                            syn = (synapseData.presynapticCell - offset, synapseData.permanence)
                            synapseList.append(syn)

                        synapseIdx += 1

                    synapsesBySource[sourcePath] = {
                        'active': activeSynapses,
                        'inactive-syn': inactiveSynapses,
                        'disconnected': disconnectedSynapses,
                    }
                    offset += width

                segs.append({
                    "synapses": synapsesBySource,
                    "nConnectedActive": nConnectedActive,
                    "nConnectedTotal": nConnectedTotal,
                    "nDisconnectedActive": nDisconnectedActive,
                    "nDisconnectedTotal": nDisconnectedTotal,
                })
            segsByColCell[col][cell] = segs

    return segsByColCell

# TODO sourcePath is a hack
def distalSegmentsFromTP(tp, onlyColumns, activeBits, sourcePath,
                         onlyActiveSynapses, onlyConnectedSynapses):
    segsByColCell = {}
    for col in onlyColumns:
        segsByColCell[col] = {}
        for cell in range(tp.cellsPerColumn):
            segs = []
            for segIdx in range(tp.getNumSegmentsInCell(col, cell)):
                v = tp.getSegmentOnCell(col, cell, segIdx)
                segData = v[0]
                activeSynapses = deque()
                inactiveSynapses = deque()
                disconnectedSynapses = deque()
                nConnectedActive = 0
                nConnectedTotal = 0
                nDisconnectedActive = 0
                nDisconnectedTotal = 0
                for targetCol, targetCell, perm in v[1:]:
                    cellId = targetCol * tp.cellsPerColumn + targetCell
                    isConnected = perm >= tp.connectedPerm
                    isActive = cellId in activeBits

                    if isConnected:
                        nConnectedTotal += 1
                    else:
                        nDisconnectedTotal += 1

                    if isActive:
                        if isConnected:
                            nConnectedActive += 1
                        else:
                            nDisconnectedActive += 1

                    synapseList = None
                    if isActive and isConnected:
                        synapseList = activeSynapses
                    elif isConnected:
                        if not onlyActiveSynapses:
                            synapseList = inactiveSynapses
                    else:
                        if not onlyConnectedSynapses:
                            synapseList = disconnectedSynapses

                    if synapseList is not None:
                        syn = (cellId, perm)
                        synapseList.append(syn)

                segs.append({
                    "synapses": {
                        sourcePath: {
                            'active': activeSynapses,
                            'inactive-syn': inactiveSynapses,
                            'disconnected': disconnectedSynapses,
                        },
                    },
                    "nConnectedActive": nConnectedActive,
                    "nConnectedTotal": nConnectedTotal,
                    "nDisconnectedActive": nDisconnectedActive,
                    "nDisconnectedTotal": nDisconnectedTotal,
                })
            segsByColCell[col][cell] = segs

    return segsByColCell

class CLASanityModel(SanityModel):
    """
    Abstract base class. Implements the query method for CLAModels.
    """
    __metaclass__ = ABCMeta

    def __init__(self, model):
        super(CLASanityModel, self).__init__()
        self.model = model

    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        senses = {'concatenated': {}}
        layers = {'layer-3': {}}

        spRegion = self.model._getSPRegion().getSelf()
        spOutput = spRegion._spatialPoolerOutput
        sp = spRegion._sfdr
        tm = self.model._getTPRegion().getSelf()._tfdr

        if getNetworkLayout:
            senses['concatenated'].update({
                'dimensions': sp.getInputDimensions(),
                'ordinal': 0,
            })
            layers['layer-3'].update({
                'dimensions': sp.getColumnDimensions(),
                'cellsPerColumn': tm.cellsPerColumn,
                'ordinal': 1,
            })

        if getBitStates:
            senses['concatenated'].update({
                'activeBits': set(spRegion._spatialPoolerInput.nonzero()[0].tolist()),
            })
            npPredictedCells = tm.getPredictedState().reshape(-1).nonzero()[0]
            layers['layer-3'].update({
                "activeColumns": set(spOutput.nonzero()[0].tolist()),
                "activeCells": set(tm._getActiveState().nonzero()[0].tolist()),
                "predictiveCells": set(npPredictedCells.tolist()),
                "predictiveColumns": set(np.unique(npPredictedCells /
                                                   tm.cellsPerColumn).tolist()),
            })

        if getProximalSegments:
            assert getBitStates
            onlyActiveSynapses = proximalSegmentsQuery['onlyActiveSynapses']
            onlyConnectedSynapses = proximalSegmentsQuery['onlyConnectedSynapses']
            sourcePath = ('senses', 'concatenated')
            proximalSegments = proximalSegmentsFromSP(sp,
                                                      senses['concatenated']['activeBits'],
                                                      onlyActiveSynapses,
                                                      onlyConnectedSynapses,
                                                      sourcePath)

            layers['layer-3'].update({
                'proximalSegments': proximalSegments,
            })

        if getDistalSegments:
            assert getBitStates
            try:
                prevState = bitHistory.next()
                columnsToCheck = (layers['layer-3']['activeColumns'] |
                                  prevState['layers']['layer-3']['predictiveColumns'])
                onlySources = prevState['layers']['layer-3']['activeCells']
                sourcePath = ('layers', 'layer-3')
                onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                if hasattr(tm, "connections"):
                    distalSegments = segmentsFromConnections(tm.connections, tm,
                                                             columnsToCheck,
                                                             onlySources,
                                                             sourcePath,
                                                             onlyActiveSynapses,
                                                             onlyConnectedSynapses)
                else:
                    distalSegments = distalSegmentsFromTP(tm, columnsToCheck,
                                                          onlySources,
                                                          sourcePath,
                                                          onlyActiveSynapses,
                                                          onlyConnectedSynapses)
                layers['layer-3'].update({
                    'distalSegments': distalSegments,
                    "nDistalLearningThreshold": tm.minThreshold,
                    "nDistalStimulusThreshold": tm.activationThreshold,
                })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'layers': layers,
        }



class ExtendedTemporalMemorySanityModel(SanityModel):
    def __init__(self, etm):
        super(ExtendedTemporalMemorySanityModel, self).__init__()
        self.tm = etm
        self.activeColumns = []
        self.activeExternalCellsBasal = []
        self.activeExternalCellsApical = []

    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        tm = self.tm

        senses = {
            'external': {}
        }
        layers = {
            'tm': {},
            'higher': {},
        }

        if getNetworkLayout:
            senses['external'].update({
                'dimensions': [tm.getBasalInputSize()],
                'ordinal': 0,
            })

            layers['tm'].update({
                'cellsPerColumn': tm.getCellsPerColumn(),
                'dimensions': (tm.numberOfColumns(),),
                'ordinal': 1,
            })

            layers['higher'].update({
                'cellsPerColumn': 1,
                'dimensions': (tm.getApicalInputSize(),),
                'ordinal': 2,
            })

        if getBitStates:
            senses['external'].update({
                'activeBits': set(self.activeExternalCellsBasal)
            })

            predictedCells = tm.getPredictedCells()
            layers['tm'].update({
                'activeColumns': set(self.activeColumns),
                'activeCells': set(tm.getActiveCells()),
                'predictedCells': set(predictedCells),
                'predictedColumns': set(predictedCells / tm.getCellsPerColumn()),
            })

            layers['higher'].update({
                'activeColumns': set(self.activeExternalCellsApical),
                'activeCells': set(self.activeExternalCellsApical),
                'predictedCells': set(),
                'predictedColumns': set(),
            })

        if getDistalSegments or getApicalSegments:
            assert getBitStates
            try:
                prevState = bitHistory.next()

                if getDistalSegments:
                    if distalSegmentsQuery['onlyNoteworthyColumns']:
                        columnsToCheck = (layers['tm']['activeColumns'] |
                                          layers['tm']['predictedColumns'])
                    else:
                        columnsToCheck = xrange(self.tm.numberOfColumns())

                    activeBits = senses['external']['activeBits']

                    inputsAndWidths = [
                        (('senses', 'external'), tm.getBasalInputSize())
                    ]
                    onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                    onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                    distalSegments = segmentsFromConnections2(tm.basalConnections, tm,
                                                              columnsToCheck, activeBits,
                                                              onlyActiveSynapses,
                                                              onlyConnectedSynapses,
                                                              inputsAndWidths)
                    layers['tm'].update({
                        'distalSegments': distalSegments,
                        "nDistalLearningThreshold": tm.getMinThreshold(),
                        "nDistalStimulusThreshold": tm.getActivationThreshold(),
                    })
                if getApicalSegments:
                    if apicalSegmentsQuery['onlyNoteworthyColumns']:
                        columnsToCheck = (layers['tm']['activeColumns'] |
                                          layers['tm']['predictedColumns'])
                    else:
                        columnsToCheck = xrange(self.tm.numberOfColumns())

                    activeBits = prevState['layers']['tm']['activeCells']

                    activeBits.update(cell + tm.numberOfCells()
                                      for cell in prevState['layers']['higher']['activeCells'])

                    sourceCellsPerColumn = 1
                    inputsAndWidths = [
                        (('layers', 'higher'), tm.getApicalInputSize()) # TODO
                    ]
                    sourceCellOffset = -tm.numberOfCells()
                    onlyActiveSynapses = apicalSegmentsQuery['onlyActiveSynapses']
                    onlyConnectedSynapses = apicalSegmentsQuery['onlyConnectedSynapses']
                    apicalSegments = segmentsFromConnections2(tm.apicalConnections, tm,
                                                              columnsToCheck, activeBits,
                                                              onlyActiveSynapses,
                                                              onlyConnectedSynapses,
                                                              inputsAndWidths)
                    layers['tm'].update({
                        'apicalSegments': apicalSegments,
                        "nApicalLearningThreshold": tm.getMinThreshold(),
                        "nApicalStimulusThreshold": tm.getActivationThreshold(),
                    })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'layers': layers,
        }


class TemporalMemorySanityModel(SanityModel):
    def __init__(self, tm):
        super(TemporalMemorySanityModel, self).__init__()
        self.tm = tm
        self.activeColumns = []
        self.activeExternalCellsBasal = []
        self.activeExternalCellsApical = []

    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        tm = self.tm

        senses = {
        }
        layers = {
            'tm': {},
        }

        if getNetworkLayout:
            layers['tm'].update({
                'cellsPerColumn': tm.getCellsPerColumn(),
                'dimensions': tm.getColumnDimensions(),
                'ordinal': 1,
            })

        if getBitStates:
            predictiveCells = set(tm.getPredictiveCells())
            predictiveColumns = set(cell / tm.getCellsPerColumn() for cell in predictiveCells)
            layers['tm'].update({
                'activeColumns': set(self.activeColumns),
                'activeCells': set(tm.getActiveCells()),
                'predictiveCells': predictiveCells,
                'predictiveColumns': predictiveColumns,
            })

        if getDistalSegments:
            assert getBitStates
            try:
                prevState = bitHistory.next()

                if distalSegmentsQuery['onlyNoteworthyColumns']:
                    columnsToCheck = (layers['tm']['activeColumns'] |
                                      prevState['layers']['tm']['predictiveColumns'])
                else:
                    columnsToCheck = xrange(self.tm.numberOfColumns())

                activeBits = prevState['layers']['tm']['activeCells']

                inputsAndWidths = [
                    (('layers', 'tm'), tm.numberOfCells()),
                ]
                onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                distalSegments = segmentsFromConnections2(tm.connections, tm,
                                                          columnsToCheck, activeBits,
                                                          onlyActiveSynapses,
                                                          onlyConnectedSynapses,
                                                          inputsAndWidths)
                layers['tm'].update({
                    'distalSegments': distalSegments,
                    "nDistalLearningThreshold": tm.getMinThreshold(),
                    "nDistalStimulusThreshold": tm.getActivationThreshold(),
                })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'layers': layers,
        }


def segmentsFromSegmentSparseMatrix(
        connections, tm, onlyColumns, activeBits,
        onlyActiveSynapses, onlyConnectedSynapses, inputsAndWidths):
    segsByColCell = {}
    for col in onlyColumns:
        segsByColCell[col] = {}
        for cell in range(tm.cellsPerColumn):
            segs = []
            for seg in connections.getSegmentsForCell(col * tm.cellsPerColumn + cell):
                nConnectedActive = 0
                nConnectedTotal = 0
                nDisconnectedActive = 0
                nDisconnectedTotal = 0
                synapsesBySource = {}

                row = connections.matrix.getRow(seg)
                presynapticCells = np.flatnonzero(row)

                offset = 0
                synapseIdx = 0
                for sourcePath, width in inputsAndWidths:
                    activeSynapses = deque()
                    inactiveSynapses = deque()
                    disconnectedSynapses = deque()
                    while (synapseIdx < len(presynapticCells) and
                           presynapticCells[synapseIdx] < offset + width):
                        presynapticCell = presynapticCells[synapseIdx]
                        permanence = row[presynapticCell]

                        isConnected = permanence >= tm.connectedPermanence
                        isActive = presynapticCell in activeBits

                        if isConnected:
                            nConnectedTotal += 1
                        else:
                            nDisconnectedTotal += 1

                        if isActive:
                            if isConnected:
                                nConnectedActive += 1
                            else:
                                nDisconnectedActive += 1

                        synapseList = None
                        if isActive and isConnected:
                            synapseList = activeSynapses
                        elif isConnected:
                            if not onlyActiveSynapses:
                                synapseList = inactiveSynapses
                        else:
                            if not onlyConnectedSynapses:
                                synapseList = disconnectedSynapses

                        if synapseList is not None:
                            syn = (presynapticCell - offset, permanence)
                            synapseList.append(syn)

                        synapseIdx += 1

                    synapsesBySource[sourcePath] = {
                        'active': activeSynapses,
                        'inactive-syn': inactiveSynapses,
                        'disconnected': disconnectedSynapses,
                    }
                    offset += width

                segs.append({
                    "synapses": synapsesBySource,
                    "nConnectedActive": nConnectedActive,
                    "nConnectedTotal": nConnectedTotal,
                    "nDisconnectedActive": nDisconnectedActive,
                    "nDisconnectedTotal": nDisconnectedTotal,
                })
            segsByColCell[col][cell] = segs

    return segsByColCell



class SMTMSequenceSanityModel(SanityModel):
    def __init__(self, tm):
        super(SMTMSequenceSanityModel, self).__init__()
        self.tm = tm
        self.activeColumns = []
        self.activeExternalCellsBasal = []
        self.activeExternalCellsApical = []

    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        tm = self.tm

        senses = {
        }
        layers = {
            'tm': {},
        }

        if getNetworkLayout:
            layers['tm'].update({
                'cellsPerColumn': tm.cellsPerColumn,
                'dimensions': (tm.columnCount,),
                'ordinal': 1,
            })

        if getBitStates:
            predictedCells = tm.getPredictedCells()
            layers['tm'].update({
                'activeColumns': set(self.activeColumns),
                'activeCells': set(tm.activeCells),
                'predictedCells': set(predictedCells),
                'predictedColumns': set(predictedCells / tm.cellsPerColumn),
            })

        if getDistalSegments:
            assert getBitStates
            try:
                prevState = bitHistory.next()

                if distalSegmentsQuery['onlyNoteworthyColumns']:
                    columnsToCheck = (layers['tm']['activeColumns'] |
                                      layers['tm']['predictedColumns'])
                else:
                    columnsToCheck = xrange(self.tm.columnCount)

                activeBits = prevState['layers']['tm']['activeCells']

                sourcePath = ('layers', 'tm')
                inputsAndWidths = [
                    (('layers', 'tm'), tm.columnCount * tm.cellsPerColumn),
                ]
                onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                distalSegments = segmentsFromSegmentSparseMatrix(
                    tm.basalConnections, tm,
                    columnsToCheck, activeBits,
                    onlyActiveSynapses,
                    onlyConnectedSynapses,
                    inputsAndWidths)
                layers['tm'].update({
                    'distalSegments': distalSegments,
                    "nDistalLearningThreshold": tm.minThreshold,
                    "nDistalStimulusThreshold": tm.activationThreshold,
                })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'layers': layers,
        }



class SMTMExternalSanityModel(SanityModel):
    def __init__(self, etm):
        super(SMTMExternalSanityModel, self).__init__()
        self.tm = etm
        self.activeColumns = []
        self.activeExternalCellsBasal = []
        self.activeExternalCellsApical = []

    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        tm = self.tm

        senses = {
            'external': {}
        }
        layers = {
            'tm': {},
            'higher': {},
        }

        if getNetworkLayout:
            senses['external'].update({
                'dimensions': (tm.basalConnections.matrix.nCols(),),
                'ordinal': 0,
            })

            layers['tm'].update({
                'cellsPerColumn': tm.getCellsPerColumn(),
                'dimensions': (tm.numberOfColumns(),),
                'ordinal': 1,
            })

            layers['higher'].update({
                'cellsPerColumn': 1,
                'dimensions': (tm.apicalConnections.matrix.nCols(),),
                'ordinal': 2,
            })

        if getBitStates:
            senses['external'].update({
                'activeBits': set(self.activeExternalCellsBasal)
            })

            predictedCells = tm.getPredictedCells()
            layers['tm'].update({
                'activeColumns': set(self.activeColumns),
                'activeCells': set(tm.getActiveCells()),
                'predictedCells': set(predictedCells),
                'predictedColumns': set(predictedCells / tm.cellsPerColumn),
            })

            layers['higher'].update({
                'activeColumns': set(self.activeExternalCellsApical),
                'activeCells': set(self.activeExternalCellsApical),
                'predictedCells': set(),
                'predictedColumns': set(),
            })

        if getDistalSegments or getApicalSegments:
            assert getBitStates
            try:
                prevState = bitHistory.next()

                if getDistalSegments:
                    if distalSegmentsQuery['onlyNoteworthyColumns']:
                        columnsToCheck = (layers['tm']['activeColumns'] |
                                          layers['tm']['predictedColumns'])
                    else:
                        columnsToCheck = xrange(self.tm.columnCount)

                    activeBits = senses['external']['activeBits']

                    inputsAndWidths = [
                        (('senses', 'external'), tm.basalConnections.matrix.nCols()),
                    ]
                    onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                    onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                    distalSegments = segmentsFromSegmentSparseMatrix(
                        tm.basalConnections, tm,
                        columnsToCheck, activeBits,
                        onlyActiveSynapses,
                        onlyConnectedSynapses,
                        inputsAndWidths)
                    layers['tm'].update({
                        'distalSegments': distalSegments,
                        "nDistalLearningThreshold": tm.minThreshold,
                        "nDistalStimulusThreshold": tm.activationThreshold,
                    })
                if getApicalSegments:
                    if apicalSegmentsQuery['onlyNoteworthyColumns']:
                        columnsToCheck = (layers['tm']['activeColumns'] |
                                          layers['tm']['predictedColumns'])
                    else:
                        columnsToCheck = xrange(self.tm.columnCount)

                    activeBits = layers['higher']['activeCells']

                    sourceCellsPerColumn = 1
                    inputsAndWidths = [
                        (('layers', 'higher'), tm.apicalConnections.matrix.nCols()),
                    ]
                    sourceCellOffset = -tm.columnCount * tm.cellsPerColumn
                    onlyActiveSynapses = apicalSegmentsQuery['onlyActiveSynapses']
                    onlyConnectedSynapses = apicalSegmentsQuery['onlyConnectedSynapses']
                    apicalSegments = segmentsFromSegmentSparseMatrix(
                        tm.apicalConnections, tm,
                        columnsToCheck, activeBits,
                        onlyActiveSynapses,
                        onlyConnectedSynapses,
                        inputsAndWidths)
                    layers['tm'].update({
                        'apicalSegments': apicalSegments,
                        "nApicalLearningThreshold": tm.minThreshold,
                        "nApicalStimulusThreshold": tm.activationThreshold,
                    })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'layers': layers,
        }



class SPTMModel(SanityModel):
    def __init__(self, sp, tm):
        super(SPTMModel, self).__init__()
        self.sp = sp
        self.tm = tm
        self.inputDisplayText = ""
        self.activeInputs = ()
        self.activeColumns = ()
        self.predictedCells = ()


    def step(self):
        assert False


    def getInputDisplayText(self):
        if isinstance(self.inputDisplayText, Mapping):
            return self.inputDisplayText.items()
        else:
            return self.inputDisplayText


    def query(self, bitHistory, getNetworkLayout=False, getBitStates=False,
              getProximalSegments=False, proximalSegmentsQuery={},
              getDistalSegments=False, distalSegmentsQuery={},
              getApicalSegments=False, apicalSegmentsQuery={}):
        tm = self.tm
        sp = self.sp

        senses = {
            'concatenated': {},
        }
        layers = {
            'sp+tm': {},
        }

        if getNetworkLayout:
            senses['concatenated'].update({
                'dimensions': sp.getInputDimensions(),
                'ordinal': 0,
            })

            layers['sp+tm'].update({
                'cellsPerColumn': tm.getCellsPerColumn(),
                'dimensions': sp.getColumnDimensions(),
                'ordinal': 1,
            })

        if getBitStates:
            senses['concatenated'].update({
                'activeBits': set(self.activeInputs)
            })

            predictedColumns = set(cell / tm.getCellsPerColumn()
                                   for cell in self.predictedCells)
            layers['sp+tm'].update({
                'activeColumns': set(self.activeColumns),
                'activeCells': set(tm.getActiveCells()),
                'predictedCells': set(self.predictedCells),
                'predictedColumns': predictedColumns,
            })

        if getProximalSegments:
            onlyActiveSynapses = proximalSegmentsQuery['onlyActiveSynapses']
            onlyConnectedSynapses = proximalSegmentsQuery['onlyConnectedSynapses']
            sourcePath = ('senses', 'concatenated')
            proximalSegments = proximalSegmentsFromSP(
                sp, senses['concatenated']['activeBits'],
                onlyActiveSynapses, onlyConnectedSynapses,
                sourcePath)

            layers['sp+tm'].update({
                'proximalSegments': proximalSegments,
            })

        if getDistalSegments:
            try:
                prevState = bitHistory.next()

                if distalSegmentsQuery['onlyNoteworthyColumns']:
                    columnsToCheck = (
                        layers['sp+tm']['activeColumns'] |
                        layers['sp+tm']['predictedColumns'])
                else:
                    columnsToCheck = xrange(sp.getNumColumns())

                activeBits = prevState['layers']['sp+tm']['activeCells']

                inputsAndWidths = [
                    (('layers', 'sp+tm'), tm.numberOfCells()),
                ]
                onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                distalSegments = segmentsFromConnections2(
                    tm.connections, tm,
                    columnsToCheck, activeBits,
                    onlyActiveSynapses,
                    onlyConnectedSynapses,
                    inputsAndWidths)

                layers['sp+tm'].update({
                    'distalSegments': distalSegments,
                    "nDistalLearningThreshold": tm.getMinThreshold(),
                    "nDistalStimulusThreshold": tm.getActivationThreshold(),
                })
            except StopIteration:
                # No previous timestep available.
                pass

        return {
            'senses': senses,
            'layers': layers,
        }
