import collections

def expandSegmentSelector(segSelector, segsByCol, defaultCells):
    if isinstance(segSelector, collections.Mapping):
        useSpecificCells = True
        columns = segSelector.keys()
    else:
        useSpecificCells = False
        columns = segSelector

    for col in columns:
        if useSpecificCells:
            selectorWithinCol = segSelector[col]
            if isinstance(selectorWithinCol, collections.Mapping):
                useSpecificSegments = True
                cells = selectorWithinCol.keys()
            else:
                useSpecificSegments = False
                cells = selectorWithinCol
        else:
            useSpecificSegments = False
            cells = defaultCells

        segIndicesByCell = {}
        for cell in cells:
            if useSpecificSegments:
                segIndicesByCell[cell] = selectorWithinCol[cell]
            else:
                if col in segsByCol:
                    segIndicesByCell[cell] = xrange(len(segsByCol[col][cell]))
                else:
                    segIndicesByCell[cell] = []

        yield (col, segIndicesByCell)


def parseSegmentSelector(segSelector):
    """Returns a column gating function that takes in a column number. If this
    column is included in the selector, it returns a cell gating function.
    Otherwise it returns None.

    Continuing this pattern, this second function takes in a cell index. It
    returns a segment gating function or None.

    The segment gating function returns True or False.

    """
    if isinstance(segSelector, collections.Mapping):
        useSpecificCells = True
        columns = segSelector.keys()
    else:
        useSpecificCells = False
        columns = segSelector

    def columnGate(column):
        if column in columns:
            if useSpecificCells:
                selectorWithinCol = segSelector[column]
                useSpecificSegments = isinstance(selectorWithinCol, collections.Mapping)
                def cellGate(cell):
                    if cell in selectorWithinCol:
                        if useSpecificSegments:
                            def segmentGate(segIndex):
                                return segIndex in selectorWithinCol[cell]
                            return segmentGate
                        else:
                            def allowAllSegments(segIndex):
                                return True
                            return allowAllSegments
                return cellGate
            else:
                def allowAllCells(cell):
                    def allowAllSegments(segIndex):
                        return True
                    return allowAllSegments
                return allowAllCells

    return columnGate

class Journal(object):
    def __init__(self, sanityModel, captureOptions=None):
        self.journal = []
        self.subscribers = []
        self.nextSnapshotId = 0

        if captureOptions is not None:
            self.captureOptions = captureOptions
        else:
            # The captureOptions and networkShape are shared with the client.
            # Use hyphenated keys for these public formats.
            self.captureOptions = {
                'keep-steps': 50,
                'ff-synapses': {
                    'capture?': False,
                    'only-active?': True,
                    'only-connected?': True,
                },
                'distal-synapses': {
                    'capture?': False,
                    'only-active?': True,
                    'only-connected?': True,
                    'only-noteworthy-columns?': True,
                },
                'apical-synapses': {
                    'capture?': False,
                    'only-active?': True,
                    'only-connected?': True,
                    'only-noteworthy-columns?': True,
                },
            }

        networkLayout = sanityModel.query(self.getBitHistory, getNetworkLayout=True)
        self.networkShape = {
            'senses': {},
            'regions': {},
        }
        for senseId, sense in networkLayout['senses'].items():
            self.networkShape['senses'][senseId] = {
                'ordinal': sense['ordinal'],
                'dimensions': sense['dimensions'],
            }
        for rgnId, rgn in networkLayout['regions'].items():
            self.networkShape['regions'][rgnId] = {}
            for lyrId, lyr in rgn.items():
                self.networkShape['regions'][rgnId][lyrId] = {
                    'ordinal': lyr['ordinal'],
                    'cells-per-column': lyr['cellsPerColumn'],
                    'dimensions': lyr['dimensions'],
                }

        self.append(sanityModel)
        sanityModel.addEventListener('didStep', lambda: self.append(sanityModel))

    # Act like a channel.
    def put(self, v):
        self.handleMessage(v)

    def getBitHistory(self):
        # Don't store this return value for too long.
        # It's invalid after self.journal is modified.
        for entry in reversed(self.journal):
            ret = {
                'senses': {},
                'regions': {},
            }

            for senseName, senseData in entry['senses'].items():
                ret['senses'][senseName] = {
                    'activeBits': senseData['activeBits'],
                }

            for regionName, regionData in entry['regions'].items():
                ret['regions'][regionName] = {}
                for layerName, layerData in regionData.items():
                    ret['regions'][regionName][layerName] = {
                        'activeCells': layerData['activeCells'],
                        'activeColumns': layerData['activeColumns'],
                        'predictedCells': layerData['predictedCells'],
                        'predictedColumns': layerData['predictedColumns'],
                    }

            yield ret

    def append(self, sanityModel):
        queryArgs = {
            'bitHistory': self.getBitHistory(),
            'getBitStates': True,
        }

        if self.captureOptions['ff-synapses']['capture?']:
            onlyActive = self.captureOptions['ff-synapses']['only-active?']
            onlyConnected = self.captureOptions['ff-synapses']['only-connected?']
            queryArgs.update({
                'getProximalSegments': True,
                'proximalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                },
            })

        if self.captureOptions['distal-synapses']['capture?']:
            onlyActive = self.captureOptions['distal-synapses']['only-active?']
            onlyConnected = self.captureOptions['distal-synapses']['only-connected?']
            onlyNoteworthy = self.captureOptions['distal-synapses']['only-noteworthy-columns?']
            queryArgs.update({
                'getDistalSegments': True,
                'distalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                    'onlyNoteworthyColumns': onlyNoteworthy,
                },
            })

        if self.captureOptions['apical-synapses']['capture?']:
            onlyActive = self.captureOptions['apical-synapses']['only-active?']
            onlyConnected = self.captureOptions['apical-synapses']['only-connected?']
            onlyNoteworthy = self.captureOptions['apical-synapses']['only-noteworthy-columns?']
            queryArgs.update({
                'getApicalSegments': True,
                'apicalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                    'onlyNoteworthyColumns': onlyNoteworthy,
                },
            })

        modelData = sanityModel.query(**queryArgs)
        self.journal.append(modelData)

        # TODO: only keep nKeepSteps models

        snapshotId = self.nextSnapshotId
        self.nextSnapshotId += 1

        step = {
            'snapshot-id': snapshotId,
            'timestep': sanityModel.timestep,
            'display-value': sanityModel.getInputDisplayText()
        }

        for subscriber in self.subscribers:
            subscriber.put(step)

    def handleMessage(self, msg):
        command = msg[0]
        args = msg[1:]
        if command == 'connect':
            pass
        elif command == 'ping':
            pass
        elif command == 'subscribe':
            stepsChannelMarshal, = args
            self.subscribers.append(stepsChannelMarshal.ch)

        elif command == 'get-network-shape':
            responseChannelMarshal, = args
            responseChannelMarshal.ch.put(self.networkShape)

        elif command == 'get-capture-options':
            responseChannelMarshal, = args
            responseChannelMarshal.ch.put(self.captureOptions)

        elif command == 'get-apical-segments':
            snapshotId, rgnId, lyrId, segSelector, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            segsByCol = layerData.get('apicalSegments', {})

            layerTemplate = self.networkShape['regions'][rgnId][lyrId]
            defaultCells = range(layerTemplate['cells-per-column'])
            selectedIndices = expandSegmentSelector(segSelector, segsByCol, defaultCells)

            ret = {}
            for col, segIndicesByCell in selectedIndices:
                ret[col] = {}
                for cellIndex, segIndices in segIndicesByCell.items():
                    ret[col][cellIndex] = {}
                    for segIndex in segIndices:
                        segment = segsByCol[col][cellIndex][segIndex]
                        ret[col][cellIndex][segIndex] = {
                            'n-conn-act': segment['nConnectedActive'],
                            'n-conn-tot': segment['nConnectedTotal'],
                            'n-disc-act': segment['nDisconnectedActive'],
                            'n-disc-tot': segment['nDisconnectedTotal'],
                            'stimulus-th': layerData['nApicalStimulusThreshold'],
                            'learning-th': layerData['nApicalLearningThreshold'],
                        }

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-distal-segments':
            snapshotId, rgnId, lyrId, segSelector, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            segsByCol = layerData.get('distalSegments', {})

            layerTemplate = self.networkShape['regions'][rgnId][lyrId]
            defaultCells = range(layerTemplate['cells-per-column'])
            selectedIndices = expandSegmentSelector(segSelector, segsByCol, defaultCells)

            ret = {}
            for col, segIndicesByCell in selectedIndices:
                ret[col] = {}
                for cellIndex, segIndices in segIndicesByCell.items():
                    ret[col][cellIndex] = {}
                    for segIndex in segIndices:
                        segment = segsByCol[col][cellIndex][segIndex]
                        ret[col][cellIndex][segIndex] = {
                            'n-conn-act': segment['nConnectedActive'],
                            'n-conn-tot': segment['nConnectedTotal'],
                            'n-disc-act': segment['nDisconnectedActive'],
                            'n-disc-tot': segment['nDisconnectedTotal'],
                            'stimulus-th': layerData['nDistalStimulusThreshold'],
                            'learning-th': layerData['nDistalLearningThreshold'],
                        }

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-proximal-segments':
            snapshotId, rgnId, lyrId, segSelector, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            segsByCol = layerData.get('proximalSegments', {})

            defaultCells = [-1]
            selectedIndices = expandSegmentSelector(segSelector, segsByCol, [-1])

            ret = {}
            for col, segIndicesByCell in selectedIndices:
                ret[col] = {}
                for cellIndex, segIndices in segIndicesByCell.items():
                    ret[col][cellIndex] = {}
                    for segIndex in segIndices:
                        segment = segsByCol[col][cellIndex][segIndex]
                        ret[col][cellIndex][segIndex] = {}

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-layer-stats':
            snapshotId, rgnId, lyrId, fetches, responseChannelMarshal = args

            if snapshotId > 0:
                prevModelData = self.journal[snapshotId - 1]
                prevLayerData = prevModelData['regions'][rgnId][lyrId]
                prevPredColumns = prevLayerData['predictedColumns']
            else:
                prevPredColumns = set()

            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            activeColumns = layerData['activeColumns']

            ret = {}

            if 'n-unpredicted-active-columns' in fetches:
                ret['n-unpredicted-active-columns'] = len(activeColumns - prevPredColumns)

            if 'n-predicted-inactive-columns' in fetches:
                ret['n-predicted-inactive-columns'] = len(prevPredColumns - activeColumns)

            if 'n-predicted-active-columns' in fetches:
                ret['n-predicted-active-columns'] = len(activeColumns & prevPredColumns)

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-apical-synapses':
            snapshotId, rgnId, lyrId, segSelector, synStates, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            segsByCol = layerData.get('apicalSegments', {})

            layerTemplate = self.networkShape['regions'][rgnId][lyrId]
            defaultCells = range(layerTemplate['cells-per-column'])
            selectedIndices = expandSegmentSelector(segSelector, segsByCol, defaultCells)

            response = self.getSynapsesResponse(segsByCol, selectedIndices, synStates, -1)
            responseChannelMarshal.ch.put(response)

        elif command == 'get-distal-synapses':
            snapshotId, rgnId, lyrId, segSelector, synStates, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            segsByCol = layerData.get('distalSegments', {})

            layerTemplate = self.networkShape['regions'][rgnId][lyrId]
            defaultCells = range(layerTemplate['cells-per-column'])
            selectedIndices = expandSegmentSelector(segSelector, segsByCol, defaultCells)

            response = self.getSynapsesResponse(segsByCol, selectedIndices, synStates, -1)
            responseChannelMarshal.ch.put(response)

        elif command == 'get-proximal-synapses':
            snapshotId, rgnId, lyrId, segSelector, synStates, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            segsByCol = layerData.get('proximalSegments', {})

            defaultCells = [-1]
            selectedIndices = expandSegmentSelector(segSelector, segsByCol, defaultCells)

            response = self.getSynapsesResponse(segsByCol, selectedIndices, synStates, 0)

            responseChannelMarshal.ch.put(response)

        elif command == 'get-column-cells':
            snapshotId, rgnId, lyrId, col, fetches, responseChannelMarshal = args
            modelData = self.journal[snapshotId]
            layerData = modelData['regions'][rgnId][lyrId]
            layerTemplate = self.networkShape['regions'][rgnId][lyrId]
            cellsPerColumn = layerTemplate['cells-per-column']
            firstCellInCol = col * cellsPerColumn
            activeCellsInCol = set(cellId - firstCellInCol
                                   for cellId in layerData['activeCells']
                                   if (cellId >= firstCellInCol and
                                       cellId < firstCellInCol + cellsPerColumn))
            predictedCellsInCol = []
            if snapshotId > 0:
                prevModelData = self.journal[snapshotId - 1]
                prevLayerData = prevModelData['regions'][rgnId][lyrId]
                predictedCellsInCol = set(cellId - firstCellInCol
                                          for cellId in prevLayerData['predictedCells']
                                          if (cellId >= firstCellInCol and
                                              cellId < firstCellInCol + cellsPerColumn))

            ret = {}

            if 'active-cells' in fetches:
                ret['active-cells'] = activeCellsInCol

            if 'prior-predicted-cells' in fetches:
                ret['prior-predicted-cells'] = predictedCellsInCol

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-layer-bits':
            snapshotId, rgnId, lyrId, fetches, cachedOnscreenBits, responseChannelMarshal = args

            ret = {}
            if 'active-columns' in fetches:
                layerData = self.journal[snapshotId]['regions'][rgnId][lyrId]
                ret['active-columns'] = layerData['activeColumns']

            if 'pred-columns' in fetches:
                if snapshotId > 0:
                    prevLayerData = self.journal[snapshotId - 1]['regions'][rgnId][lyrId]
                    ret['pred-columns'] = prevLayerData['predictedColumns']

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-sense-bits':
            snapshotId, senseId, fetches, cachedOnscreenBits, responseChannelMarshal = args
            senseData = self.journal[snapshotId]['senses'][senseId]

            ret = {}
            if 'active-bits' in fetches:
                ret['active-bits'] = senseData['activeBits']

            responseChannelMarshal.ch.put(ret)

        elif command == 'set-capture-options':
            captureOptions, = args
            self.captureOptions = captureOptions

        else:
            print "Unrecognized command! %s" % command

    def getSynapsesResponse(self, segsByCol, selectedIndices, synStates, dt):
        ret = {}
        for col, segIndicesByCell in selectedIndices:
            ret[col] = {}
            for cellIndex, segIndices in segIndicesByCell.items():
                ret[col][cellIndex] = {}
                for segIndex in segIndices:
                    ret[col][cellIndex][segIndex] = {}
                    segment = segsByCol[col][cellIndex][segIndex]
                    for sourcePath, synapsesByState in segment['synapses'].items():
                        synapseTemplate = {}
                        synapseTemplate['src-id'] = sourcePath[1]
                        if sourcePath[0] == 'regions':
                            synapseTemplate['src-lyr'] = sourcePath[2]

                        for state, synapses in synapsesByState.items():
                            if state in synStates:
                                syns = []
                                for sourceBit, perm in synapses:
                                    # TODO use synapse permanence from the
                                    # beginning of the timestep. Otherwise we're
                                    # calculating which synapses were active
                                    # using the post-learning permanences. (Only
                                    # in the visualization layer, not NuPIC
                                    # itself)
                                    syn = synapseTemplate.copy()
                                    syn.update({
                                        "src-i": sourceBit,
                                        "perm": perm,
                                        "src-dt": dt, # TODO don't assume this
                                    })
                                    syns.append(syn)

                                if state not in ret[col][cellIndex][segIndex]:
                                    ret[col][cellIndex][segIndex][state] = []

                                ret[col][cellIndex][segIndex][state].extend(syns)

        return ret
