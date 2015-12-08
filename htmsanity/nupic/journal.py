from collections import deque

class Journal(object):
    def __init__(self, sanityModel):
        self.journal = []
        self.subscribers = []
        self.nextModelId = 0
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

        self.stepTemplate = sanityModel.query(self.getBitHistory, getNetworkLayout=True)
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
                'getProximalSynapses': True,
                'proximalSynapsesQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                },
            })

        if self.captureOptions['distal-synapses']['capture?']:
            onlyActive = self.captureOptions['distal-synapses']['only-active?']
            onlyConnected = self.captureOptions['distal-synapses']['only-connected?']
            queryArgs.update({
                'getDistalSegments': True,
                'distalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                },
            })

        if self.captureOptions['apical-synapses']['capture?']:
            onlyActive = self.captureOptions['apical-synapses']['only-active?']
            onlyConnected = self.captureOptions['apical-synapses']['only-connected?']
            queryArgs.update({
                'getApicalSegments': True,
                'apicalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                },
            })

        modelData = sanityModel.query(**queryArgs)
        self.journal.append(modelData)

        # TODO: only keep nKeepSteps models

        modelId = self.nextModelId
        self.nextModelId += 1

        step = {
            'model-id': modelId,
            'timestep': sanityModel.timestep,
            'senses': {},
            'regions': {},
        }

        for senseName, senseData in modelData['senses'].items():
            step['senses'][senseName] = {
                'active-bits': senseData['activeBits'],
            }

        for regionName, regionData in modelData['regions'].items():
            step['regions'][regionName] = {}
            for layerName, layerData in regionData.items():
                prevPredColumns = None
                if modelId > 0:
                    prevModelData = self.journal[modelId - 1]
                    prevLayerData = prevModelData['regions'][regionName][layerName]
                    prevPredColumns = prevLayerData['predictedColumns']
                step['regions'][regionName][layerName] = {
                    'active-columns': layerData['activeColumns'],
                    'pred-columns': prevPredColumns
                }

        step['display-value'] = sanityModel.getInputDisplayText()

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
            stepsChannelMarshal, responseChannelMarshal = args

            self.subscribers.append(stepsChannelMarshal.ch)

            responseChannelMarshal.ch.put([self.stepTemplate, self.captureOptions])

        elif command == 'get-column-apical-segments':
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][rgnId][lyrId]
            segments = layerData.get('apicalSegments', [])
            columnSegments = filter(lambda seg: (seg['column'] == col), segments)
            segmentsByCell = {}
            for segment in columnSegments:
                cell = segment['cell']
                if cell not in segmentsByCell:
                    segmentsByCell[cell] = {}
                segmentIndex = len(segmentsByCell[cell])
                segmentsByCell[cell][segmentIndex] = {
                    'n-conn-act': segment['nConnectedActive'],
                    'n-conn-tot': segment['nConnectedTotal'],
                    'n-disc-act': segment['nDisconnectedActive'],
                    'n-disc-tot': segment['nDisconnectedTotal'],
                    'stimulus-th': layerData['nApicalStimulusThreshold'],
                    'learning-th': layerData['nApicalLearningThreshold'],
                }
            responseChannelMarshal.ch.put(segmentsByCell)

        elif command == 'get-column-distal-segments':
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][rgnId][lyrId]
            segments = layerData.get('distalSegments', [])
            columnSegments = filter(lambda seg: (seg['column'] == col), segments)
            segmentsByCell = {}
            for segment in columnSegments:
                cell = segment['cell']
                if cell not in segmentsByCell:
                    segmentsByCell[cell] = {}
                segmentIndex = len(segmentsByCell[cell])
                segmentsByCell[cell][segmentIndex] = {
                    'n-conn-act': segment['nConnectedActive'],
                    'n-conn-tot': segment['nConnectedTotal'],
                    'n-disc-act': segment['nDisconnectedActive'],
                    'n-disc-tot': segment['nDisconnectedTotal'],
                    'stimulus-th': layerData['nDistalStimulusThreshold'],
                    'learning-th': layerData['nDistalLearningThreshold'],
                }
            responseChannelMarshal.ch.put(segmentsByCell)

        elif command == 'get-column-proximal-segments':
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            # Only one proximal segment per column.  And nobody is checking
            # nConnectedActive, etc., for proximal segments, so don't grab it.
            cell = -1
            segIndex = 0
            seg = {}
            response = {cell: {segIndex: seg}}
            responseChannelMarshal.ch.put(response)

        elif command == 'get-column-state-freqs':
            modelId, responseChannelMarshal = args
            modelData = self.journal[modelId]

            ret = {}
            for rgnId, regionData in modelData['regions'].items():
                for lyrId, layerData in regionData.items():
                    layerDims = self.stepTemplate['regions'][rgnId][lyrId]['dimensions']
                    size = reduce(lambda x, y: x * y, layerDims, 1)

                    activeColumns = layerData['activeColumns']
                    if modelId > 0:
                        prevModelData = self.journal[modelId - 1]
                        prevLayerData = prevModelData['regions'][rgnId][lyrId]
                        prevPredColumns = prevLayerData['predictedColumns']
                    else:
                        prevPredColumns = set()

                    path = (rgnId, lyrId)
                    ret[path] = {
                        'active': len(activeColumns - prevPredColumns),
                        'predicted': len(prevPredColumns - activeColumns),
                        'active-predicted': len(activeColumns & prevPredColumns),
                        'timestep': modelId,
                        'size': size,
                    }

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-apical-segment-synapses':
            modelId, rgnId, lyrId, col, cellIndex, segIndex, synStates, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][rgnId][lyrId]
            segments = layerData.get('apicalSegments', [])
            response = self.getSegmentSynapsesResponse(segments, col, cellIndex,
                                                       segIndex, synStates)
            responseChannelMarshal.ch.put(response)

        elif command == 'get-distal-segment-synapses':
            modelId, rgnId, lyrId, col, cellIndex, segIndex, synStates, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][rgnId][lyrId]
            segments = layerData.get('distalSegments', [])
            response = self.getSegmentSynapsesResponse(segments, col, cellIndex,
                                                       segIndex, synStates)
            responseChannelMarshal.ch.put(response)

        elif command == 'get-proximal-segment-synapses':
            modelId, rgnId, lyrId, col, cellIndex, segIndex, synStates, responseChannelMarshal = args
            assert cellIndex is -1
            assert segIndex is 0
            modelData = self.journal[modelId]
            layerData = modelData['regions'][rgnId][lyrId]
            proximalSynapses = layerData.get('proximalSynapses', {})
            synsByState = {}
            for sourcePath, synapsesByState in proximalSynapses.items():
                for state, synapses in synapsesByState.items():
                    if state in synStates:
                        syns = deque()
                        synapseTemplate = {
                            'src-id': sourcePath[1],
                            'syn-state': state,
                        }
                        if sourcePath[0] == 'regions':
                            synapseTemplate['src-lyr'] = sourcePath[2]

                        for column, sourceColumn, perm in synapses:
                            if column == col:
                                syn = synapseTemplate.copy()
                                syn.update({
                                    'src-col': sourceColumn,
                                    'perm': perm,
                                    'src-dt': 0, # TODO don't assume this
                                })
                                syns.append(syn)

                        synsByState[state] = syns

            responseChannelMarshal.ch.put(synsByState)

        elif command == 'get-column-cells':
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][rgnId][lyrId]
            layerTemplate = self.stepTemplate['regions'][rgnId][lyrId]
            cellsPerColumn = layerTemplate['cellsPerColumn']
            firstCellInCol = col * cellsPerColumn
            activeCellsInCol = set(cellId - firstCellInCol
                                   for cellId in layerData['activeCells']
                                   if (cellId >= firstCellInCol and
                                       cellId < firstCellInCol + cellsPerColumn))
            predictedCellsInCol = []
            if modelId > 0:
                prevModelData = self.journal[modelId - 1]
                prevLayerData = prevModelData['regions'][rgnId][lyrId]
                predictedCellsInCol = set(cellId - firstCellInCol
                                          for cellId in prevLayerData['predictedCells']
                                          if (cellId >= firstCellInCol and
                                              cellId < firstCellInCol + cellsPerColumn))
            responseChannelMarshal.ch.put({
                'cells-per-column': cellsPerColumn,
                'active-cells': activeCellsInCol,
                'prior-predicted-cells': predictedCellsInCol,
            })

        elif command == 'get-inbits-cols':
            modelId, fetches, cachedOnscreenBits, responseChannelMarshal = args
            modelData = self.journal[modelId]

            # No extended functionality for NuPIC yet.
            response = {}

            responseChannelMarshal.ch.put(response)

        elif command == 'set-capture-options':
            captureOptions, = args
            self.captureOptions = captureOptions
        else:
            print "Unrecognized command! %s" % command

    def getSegmentSynapsesResponse(self, segments, col, cellIndex, segIndex, synStates):
        # Find the segment
        segment = None
        nextSegIndex = 0
        assert(segIndex >= 0)
        for seg in segments:
            if seg['column'] == col and seg['cell'] == cellIndex:
                if nextSegIndex == segIndex:
                    segment = seg
                    break
                else:
                    nextSegIndex += 1

        retSynsByState = {}
        for sourcePath, synapsesByState in segment['synapses'].items():
            synapseTemplate = {}
            if sourcePath:
                synapseTemplate['src-id'] = sourcePath[1]
                if sourcePath[0] == 'regions':
                    synapseTemplate['src-lyr'] = sourcePath[2]

            for state, synapses in synapsesByState.items():
                if state in synStates:
                    syns = deque()
                    for targetCol, targetCell, perm in synapses:
                        # TODO use synapse permanence from the beginning of the
                        # timestep. Otherwise we're calculating which synapses
                        # were active using the post-learning permanences.
                        # (Only in the visualization layer, not NuPIC itself)
                        syn = synapseTemplate.copy()
                        syn.update({
                            "src-col": targetCol,
                            "perm": perm,
                            "src-dt": 1, # TODO don't assume this
                        })
                        syns.append(syn)
                        retSynsByState[state] = syns
        return retSynsByState
