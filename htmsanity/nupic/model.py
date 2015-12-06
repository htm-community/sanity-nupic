from abc import ABCMeta, abstractmethod
from collections import deque

import numpy
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
            self.timestep += 1
            for fn in self.listeners['didStep'].values():
                fn()

        return ret

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
              getProximalSynapses=False, proximalSynapsesQuery={},
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
        getProximalSynapses : bool
          Whether to fetch this set of values. See the annotated return example.
        getDistalSegments : bool
          Whether to fetch this set of values. See the annotated return example.
        getApicalSegments : bool
          Whether to fetch this set of values. See the annotated return example.
        proximalSynapsesQuery : dict
          Details for the getProximalSynapses.
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
            'regions': {
                'myRegion1': {
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

                        # getProximalSynapses
                        'proximalSynapses': {
                            # Path to presynaptic layer / sense
                            ('senses', 'mySense1'): {
                                'active': [
                                    # Tuple:
                                    # - Column
                                    # - Presynaptic column
                                    # - Permanence
                                    (0, 160, 0.25),
                                    (19, 74, 0.47296399),
                                ],
                                'disconnected': [],
                                'inactive-syn': [],
                            }},

                        # getApicalSegments
                        'nDistalStimulusThreshold': 13,
                        'nDistalLearningThreshold': 9,
                        'apicalSegments': [
                            # Same format as distalSegments
                        ],

                        # getDistalSegments
                        'nDistalStimulusThreshold': 13,
                        'nDistalLearningThreshold': 9,
                        'distalSegments': [
                            {
                                'column': 0,
                                'cell': 9,
                                'nDisconnectedActive': 0,
                                'nDisconnectedTotal': 0,
                                'nConnectedActive': 6,
                                'nConnectedTotal': 10
                                'synapses': {
                                    # Path to presynaptic layer / sense
                                    ('regions', 'myRegion1', 'myLayer3'): [
                                        'active': [
                                            # Tuple:
                                            # - Presynaptic column
                                            # - Presynaptic cell (within column)
                                            # - Permanence
                                            (0, 25, 0.7100000381469727),
                                            (4, 10, 0.7100000381469727),
                                        ],
                                        'disconnected': [],
                                        'inactive-syn': [],
                                    ]
                                },
                            },
                            {
                                'column': 0,
                                'cell': 10,
                                'nDisconnectedTotal': 10,
                                'nDisconnectedActive': 7,
                                'nConnectedActive': 0,
                                'nConnectedTotal': 0
                                'synapses': {
                                    ('regions', 'myRegion1', 'myLayer3'): []
                                },
                            },
                        ],

                    }
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

def proximalSynapsesFromSP(sp, activeBits, onlyActiveSynapses,
                           onlyConnectedSynapses, sourceDepth=1):
    activeSyns = deque()
    inactiveSyns = deque()
    disconnectedSyns = deque()
    synPermConnected = sp.getSynPermConnected()
    synapsePotentials = numpy.zeros(sp.getNumInputs()).astype('uint32')
    synapsePermanences = numpy.zeros(sp.getNumInputs()).astype(GetNTAReal())
    activeMask = numpy.zeros(sp.getNumInputs(), dtype=bool)
    activeMask[list(activeBits)] = True
    for column in range(sp.getNumColumns()):
        sp.getPotential(column, synapsePotentials)
        potentialMask = synapsePotentials == 1

        sp.getPermanence(column, synapsePermanences)
        connectedMask = synapsePermanences >= synPermConnected

        activeConnectedMask = activeMask & potentialMask & connectedMask
        for inputBit in activeConnectedMask.nonzero()[0]:
            sourceColumn = int(inputBit / sourceDepth)
            syn = (column, sourceColumn, synapsePermanences[inputBit])
            activeSyns.append(syn)

        if not onlyActiveSynapses:
            inactiveConnectedMask = ~activeMask & potentialMask & connectedMask
            for inputBit in inactiveConnectedMask.nonzero()[0]:
                sourceColumn = int(inputBit / sourceDepth)
                syn = (column, sourceColumn, synapsePermanences[inputBit])
                inactiveSyns.append(syn)

        if not onlyConnectedSynapses:
            disconnectedMask = potentialMask & ~connectedMask
            if onlyActiveSynapses:
                disconnectedMask = disconnectedMask & activeMask
            for inputBit in disconnectedMask.nonzero()[0]:
                sourceColumn = int(inputBit / sourceDepth)
                syn = (column, sourceColumn, synapsePermanences[inputBit])
                disconnectedSyns.append(syn)

    return {
        'active': activeSyns,
        'inactive-syn': inactiveSyns,
        'disconnected': disconnectedSyns,
    }

# TODO sourcePath is a hack
def segmentsFromConnections(connections, tm, onlyColumns, activeBits,
                            sourcePath, sourceCellsPerColumn,
                            onlyActiveSynapses, onlyConnectedSynapses,
                            sourceCellOffset=0):
    segments = deque()
    for col in onlyColumns:
        for cell in range(tm.cellsPerColumn):
            for seg in connections.segmentsForCell(col * tm.cellsPerColumn + cell):
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

                    isConnected = synapseData.permanence >= tm.connectedPermanence
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
                        presynapticCol = presynapticCell / sourceCellsPerColumn
                        presynapticCellOffset = presynapticCell % sourceCellsPerColumn
                        syn = (presynapticCol, presynapticCellOffset, synapseData.permanence)
                        synapseList.append(syn)

                segments.append({
                    "column": col,
                    "cell": cell,
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

    return segments

# TODO sourcePath is a hack
def distalSegmentsFromTP(tp, onlyColumns, activeBits, sourcePath,
                         onlyActiveSynapses, onlyConnectedSynapses):
    distalSegments = deque()
    for col in onlyColumns:
        for cell in range(tp.cellsPerColumn):
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
                        syn = (targetCol, targetCell, perm)
                        synapseList.append(syn)

                distalSegments.append({
                    "column": col,
                    "cell": cell,
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

    return distalSegments

class CLASanityModel(SanityModel):
    """
    Abstract base class. Implements the query method for CLAModels.
    """
    __metaclass__ = ABCMeta

    def __init__(self, model):
        super(CLASanityModel, self).__init__()
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
            onlyActiveSynapses = proximalSynapsesQuery['onlyActiveSynapses']
            onlyConnectedSynapses = proximalSynapsesQuery['onlyConnectedSynapses']
            proximalSynapses = proximalSynapsesFromSP(sp,
                                                      senses['concatenated']['activeBits'],
                                                      onlyActiveSynapses,
                                                      onlyConnectedSynapses)

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
                sourcePath = ('regions', 'rgn-0', 'layer-3')
                onlyActiveSynapses = distalSegmentsQuery['onlyActiveSynapses']
                onlyConnectedSynapses = distalSegmentsQuery['onlyConnectedSynapses']
                if hasattr(tp, "connections"):
                    distalSegments = segmentsFromConnections(tp.connections, tp,
                                                             columnsToCheck,
                                                             onlySources,
                                                             sourcePath,
                                                             tp.cellsPerColumn,
                                                             onlyActiveSynapses,
                                                             onlyConnectedSynapses)
                else:
                    distalSegments = distalSegmentsFromTP(tp, columnsToCheck,
                                                          onlySources,
                                                          sourcePath,
                                                          onlyActiveSynapses,
                                                          onlyConnectedSynapses)
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
