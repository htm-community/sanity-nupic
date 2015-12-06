from collections import deque

from transit.transit_types import Keyword

class Journal(object):
    def __init__(self, sanityModel):
        self.journal = []
        self.subscribers = []
        self.nextModelId = 0
        self.captureOptions = {
            Keyword("keep-steps"): 50,
            Keyword("ff-synapses"): {
                Keyword("capture?"): False,
                Keyword("only-active?"): True,
                Keyword("only-connected?"): True,
            },
            Keyword("distal-synapses"): {
                Keyword("capture?"): False,
                Keyword("only-active?"): True,
                Keyword("only-connected?"): True,
                Keyword("only-noteworthy-columns?"): True,
            },
            Keyword("apical-synapses"): {
                Keyword("capture?"): False,
                Keyword("only-active?"): True,
                Keyword("only-connected?"): True,
                Keyword("only-noteworthy-columns?"): True,
            },
        }

        self.absorbStepTemplate(sanityModel)
        self.append(sanityModel)
        sanityModel.addEventListener('didStep', lambda: self.append(sanityModel))

    # Act like a channel.
    def put(self, v):
        self.handleMessage(v)

    def absorbStepTemplate(self, sanityModel):
        self.stepTemplate = sanityModel.query(self.getBitHistory, getNetworkLayout=True)
        senses = {}
        for name, senseData in self.stepTemplate["senses"].items():
            senses[Keyword(name)] = {
                Keyword("dimensions"): senseData["dimensions"],
                Keyword('ordinal'): senseData['ordinal'],
            }

        regions = {}
        for regionName, regionData in self.stepTemplate["regions"].items():
            region = {}
            for layerName, layerData in regionData.items():
                region[Keyword(layerName)] = {
                    Keyword("dimensions"): layerData["dimensions"],
                    Keyword('ordinal'): layerData['ordinal'],
                }
            regions[Keyword(regionName)] = region

        self.stepTemplateEncoded = {
            Keyword("senses"): senses,
            Keyword("regions"): regions,
        }

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

        if self.captureOptions[Keyword("ff-synapses")][Keyword("capture?")]:
            onlyActive = self.captureOptions[Keyword('ff-synapses')][Keyword('only-active?')]
            onlyConnected = self.captureOptions[Keyword('ff-synapses')][Keyword('only-connected?')]
            queryArgs.update({
                'getProximalSynapses': True,
                'proximalSynapsesQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                },
            })

        if self.captureOptions[Keyword("distal-synapses")][Keyword("capture?")]:
            onlyActive = self.captureOptions[Keyword('distal-synapses')][Keyword('only-active?')]
            onlyConnected = self.captureOptions[Keyword('distal-synapses')][Keyword('only-connected?')]
            queryArgs.update({
                'getDistalSegments': True,
                'distalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': onlyConnected,
                },
            })

        if self.captureOptions[Keyword("apical-synapses")][Keyword("capture?")]:
            onlyActive = self.captureOptions[Keyword('apical-synapses')][Keyword('only-active?')]
            onlyConnected = self.captureOptions[Keyword('apical-synapses')][Keyword('only-connected?')]
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
            Keyword("model-id"): modelId,
            Keyword("timestep"): sanityModel.timestep,
            Keyword("senses"): {},
            Keyword("regions"): {},
        }

        for senseName, senseData in modelData["senses"].items():
            step[Keyword("senses")][Keyword(senseName)] = {
                Keyword("active-bits"): senseData["activeBits"],
            }

        for regionName, regionData in modelData["regions"].items():
            step[Keyword("regions")][Keyword(regionName)] = {}
            for layerName, layerData in regionData.items():
                prevPredColumns = None
                if modelId > 0:
                    prevModelData = self.journal[modelId - 1]
                    prevLayerData = prevModelData['regions'][regionName][layerName]
                    prevPredColumns = prevLayerData['predictedColumns']
                step[Keyword("regions")][Keyword(regionName)][Keyword(layerName)] = {
                    Keyword("active-columns"): layerData["activeColumns"],
                    Keyword("pred-columns"): prevPredColumns
                }

        step[Keyword("display-value")] = sanityModel.getInputDisplayText()

        for subscriber in self.subscribers:
            subscriber.put(step)

    def handleMessage(self, msg):
        command = str(msg[0])
        args = msg[1:]
        if command == "connect":
            pass
        elif command == "ping":
            pass
        elif command == "subscribe":
            stepsChannelMarshal, responseChannelMarshal = args

            self.subscribers.append(stepsChannelMarshal.ch)

            responseChannelMarshal.ch.put([self.stepTemplateEncoded, self.captureOptions])

        elif command == 'get-column-apical-segments':
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            segments = layerData.get('apicalSegments', [])
            columnSegments = filter(lambda seg: (seg['column'] == col), segments)
            segmentsByCell = {}
            for segment in columnSegments:
                cell = segment['cell']
                if cell not in segmentsByCell:
                    segmentsByCell[cell] = {}
                segmentIndex = len(segmentsByCell[cell])
                segmentsByCell[cell][segmentIndex] = {
                    Keyword("n-conn-act"): segment["nConnectedActive"],
                    Keyword("n-conn-tot"): segment["nConnectedTotal"],
                    Keyword("n-disc-act"): segment["nDisconnectedActive"],
                    Keyword("n-disc-tot"): segment["nDisconnectedTotal"],
                    Keyword("stimulus-th"): layerData['nApicalStimulusThreshold'],
                    Keyword("learning-th"): layerData['nApicalLearningThreshold'],
                }
            responseChannelMarshal.ch.put(segmentsByCell)

        elif command == 'get-column-distal-segments':
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            segments = layerData.get('distalSegments', [])
            columnSegments = filter(lambda seg: (seg['column'] == col), segments)
            segmentsByCell = {}
            for segment in columnSegments:
                cell = segment['cell']
                if cell not in segmentsByCell:
                    segmentsByCell[cell] = {}
                segmentIndex = len(segmentsByCell[cell])
                segmentsByCell[cell][segmentIndex] = {
                    Keyword("n-conn-act"): segment["nConnectedActive"],
                    Keyword("n-conn-tot"): segment["nConnectedTotal"],
                    Keyword("n-disc-act"): segment["nDisconnectedActive"],
                    Keyword("n-disc-tot"): segment["nDisconnectedTotal"],
                    Keyword("stimulus-th"): layerData['nDistalStimulusThreshold'],
                    Keyword("learning-th"): layerData['nDistalLearningThreshold'],
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
            for rgnId, regionData in modelData["regions"].items():
                for lyrId, layerData in regionData.items():
                    layerDims = self.stepTemplate['regions'][rgnId][lyrId]['dimensions']
                    size = reduce(lambda x, y: x * y, layerDims, 1)

                    activeColumns = layerData["activeColumns"]
                    if modelId > 0:
                        prevModelData = self.journal[modelId - 1]
                        prevLayerData = prevModelData['regions'][rgnId][lyrId]
                        prevPredColumns = prevLayerData['predictedColumns']
                    else:
                        prevPredColumns = set()

                    path = (Keyword(rgnId), Keyword(lyrId))
                    ret[path] = {
                        Keyword('active'): len(activeColumns - prevPredColumns),
                        Keyword('predicted'): len(prevPredColumns - activeColumns),
                        Keyword('active-predicted'): len(activeColumns & prevPredColumns),
                        Keyword('timestep'): modelId,
                        Keyword('size'): size,
                    }

            responseChannelMarshal.ch.put(ret)

        elif command == 'get-apical-segment-synapses':
            modelId, rgnId, lyrId, col, cellIndex, segIndex, synStates, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            segments = layerData.get('apicalSegments', [])
            response = self.getSegmentSynapsesResponse(segments, col, cellIndex,
                                                       segIndex, synStates)
            responseChannelMarshal.ch.put(response)

        elif command == 'get-distal-segment-synapses':
            modelId, rgnId, lyrId, col, cellIndex, segIndex, synStates, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            segments = layerData.get('distalSegments', [])
            response = self.getSegmentSynapsesResponse(segments, col, cellIndex,
                                                       segIndex, synStates)
            responseChannelMarshal.ch.put(response)

        elif command == 'get-proximal-segment-synapses':
            modelId, rgnId, lyrId, col, cellIndex, segIndex, synStates, responseChannelMarshal = args
            assert cellIndex is -1
            assert segIndex is 0
            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            proximalSynapses = layerData.get('proximalSynapses', {})
            synsByState = {}
            for sourcePath, synapsesByState in proximalSynapses.items():
                for state, synapses in synapsesByState.items():
                    if Keyword(state) in synStates:
                        syns = deque()
                        synapseTemplate = {
                            Keyword('src-id'): Keyword(sourcePath[1]),
                            Keyword('syn-state'): Keyword(state),
                        }
                        if sourcePath[0] == 'regions':
                            synapseTemplate[Keyword('src-lyr')] = Keyword(sourcePath[2])

                        for column, sourceColumn, perm in synapses:
                            if column == col:
                                syn = synapseTemplate.copy()
                                syn.update({
                                    Keyword("src-col"): sourceColumn,
                                    Keyword("perm"): perm,
                                    Keyword("src-dt"): 0, # TODO don't assume this
                                })
                                syns.append(syn)

                        synsByState[Keyword(state)] = syns

            responseChannelMarshal.ch.put(synsByState)

        elif command == "get-column-cells":
            modelId, rgnId, lyrId, col, responseChannelMarshal = args
            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            layerTemplate = self.stepTemplate['regions'][str(rgnId)][str(lyrId)]
            cellsPerColumn = layerTemplate['cellsPerColumn']
            firstCellInCol = col * cellsPerColumn
            activeCellsInCol = set(cellId - firstCellInCol
                                   for cellId in layerData["activeCells"]
                                   if (cellId >= firstCellInCol and
                                       cellId < firstCellInCol + cellsPerColumn))
            predictedCellsInCol = []
            if modelId > 0:
                prevModelData = self.journal[modelId - 1]
                prevLayerData = prevModelData['regions'][str(rgnId)][str(lyrId)]
                predictedCellsInCol = set(cellId - firstCellInCol
                                          for cellId in prevLayerData['predictedCells']
                                          if (cellId >= firstCellInCol and
                                              cellId < firstCellInCol + cellsPerColumn))
            responseChannelMarshal.ch.put({
                Keyword('cells-per-column'): cellsPerColumn,
                Keyword('active-cells'): activeCellsInCol,
                Keyword('prior-predicted-cells'): predictedCellsInCol,
            })

        elif command == "get-inbits-cols":
            modelId, token, responseChannelMarshal = args
            modelData = self.journal[modelId]

            # No extended functionality for NuPIC yet.
            response = {}

            responseChannelMarshal.ch.put(response)

        elif command == "set-capture-options":
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
                synapseTemplate[Keyword('src-id')] = Keyword(sourcePath[1])
                if sourcePath[0] == 'regions':
                    synapseTemplate[Keyword('src-lyr')] = Keyword(sourcePath[2])

            for state, synapses in synapsesByState.items():
                stateKeyword = Keyword(state)
                if stateKeyword in synStates:
                    syns = deque()
                    for targetCol, targetCell, perm in synapses:
                        # TODO use synapse permanence from the beginning of the
                        # timestep. Otherwise we're calculating which synapses
                        # were active using the post-learning permanences.
                        # (Only in the visualization layer, not NuPIC itself)
                        syn = synapseTemplate.copy()
                        syn.update({
                            Keyword("src-col"): targetCol,
                            Keyword("perm"): perm,
                            Keyword("src-dt"): 1, # TODO don't assume this
                        })
                        syns.append(syn)
                        retSynsByState[stateKeyword] = syns
        return retSynsByState
