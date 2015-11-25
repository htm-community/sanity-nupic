from collections import deque

from transit.transit_types import Keyword

def makeStep(sanityModel, modelId):
    return {
        Keyword("model-id"): modelId,
        Keyword("timestep"): sanityModel.timestep,
    }

class Journal(object):
    def __init__(self, sanityModel):
        self.journal = []
        self.subscribers = []
        self.nextModelId = 0
        self.captureOptions = {
            Keyword("keep-steps"): 50,
            Keyword("ff-synapses"): {
                Keyword("capture?"): False,
                Keyword("min-perm"): 0.1, # TODO
                Keyword("only-active?"): True,
            },
            Keyword("distal-synapses"): {
                Keyword("capture?"): False,
                Keyword("min-perm"): 0.5, # TODO
                Keyword("only-active?"): True,
                Keyword("only-noteworthy-columns?"): True,
            },
            Keyword("apical-synapses"): {
                Keyword("capture?"): False,
                Keyword("min-perm"): 0.5, # TODO
                Keyword("only-active?"): True,
                Keyword("only-noteworthy-columns?"): True,
            },
        }

        self.absorbStepTemplate(sanityModel)
        self.append(sanityModel)
        sanityModel.addEventListener('didStep', lambda: self.append(sanityModel))

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
            queryArgs.update({
                'getProximalSynapses': True,
                'proximalSynapsesQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': True,
                },
            })

        if self.captureOptions[Keyword("distal-synapses")][Keyword("capture?")]:
            onlyActive = self.captureOptions[Keyword('distal-synapses')][Keyword('only-active?')]
            queryArgs.update({
                'getDistalSegments': True,
                'distalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': True,
                },
            })

        if self.captureOptions[Keyword("apical-synapses")][Keyword("capture?")]:
            onlyActive = self.captureOptions[Keyword('apical-synapses')][Keyword('only-active?')]
            queryArgs.update({
                'getApicalSegments': True,
                'apicalSegmentsQuery': {
                    'onlyActiveSynapses': onlyActive,
                    'onlyConnectedSynapses': True,
                },
            })

        self.journal.append(sanityModel.query(**queryArgs))

        # TODO: only keep nKeepSteps models

        step = makeStep(sanityModel, self.nextModelId)
        self.nextModelId += 1

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
            stepsChannel, responseChannel = args

            self.subscribers.append(stepsChannel)

            responseChannel.put([self.stepTemplateEncoded, self.captureOptions])
        elif command == "get-cells-segments":
            modelId, rgnId, lyrId, col, ci_si, token, responseChannel = args

            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            layerTemplate = self.stepTemplate['regions'][str(rgnId)][str(lyrId)]

            distalSegments = filter(lambda seg: (seg["column"] == col),
                                          layerData.get("distalSegments", []))
            apicalSegments = filter(lambda seg: (seg["column"] == col),
                                          layerData.get("apicalSegments", []))

            # TODO this is gross. We should rework the
            # get-cells-segments message. It has redundant information
            # between distal and apical segments, both messages
            # containing cell information, and with hard-to-understand
            # selection behavior.
            distal = self.getCellsSegmentsResponse(modelId, rgnId, lyrId, col, ci_si, layerData,
                                                   layerData.get("distalSegments", []),
                                                   layerTemplate['cellsPerColumn'],
                                                   "nDistalStimulusThreshold",
                                                   "nDistalLearningThreshold")
            apical = self.getCellsSegmentsResponse(modelId, rgnId, lyrId, col, ci_si, layerData,
                                                   layerData.get("apicalSegments", []),
                                                   layerTemplate['cellsPerColumn'],
                                                   "nApicalStimulusThreshold",
                                                   "nApicalLearningThreshold")

            responseChannel.put({
                Keyword('distal'): distal,
                Keyword('apical'): apical,
            })

        elif command == "get-ff-in-synapses":
            modelId, rgnId, lyrId, onlyColumns, doTraceBack, token, responseChannel = args
            modelData = self.journal[modelId]
            layerData = modelData["regions"][str(rgnId)][str(lyrId)]
            proximalSynapses = layerData.get('proximalSynapses', {})
            synapsesByColumn = {}
            for sourcePath, synapsesByState in proximalSynapses.items():
                for state, synapses in synapsesByState.items():
                    synapseTemplate = {
                        Keyword('src-id'): Keyword(sourcePath[1]),
                        Keyword('syn-state'): Keyword(state),
                    }
                    activeBits = []
                    if sourcePath[0] == 'senses':
                        senseData = modelData['senses'][sourcePath[1]]
                        activeBits = senseData['activeBits']
                    elif sourcePath[0] == 'regions':
                        synapseTemplate[Keyword('src-lyr')] = Keyword(sourcePath[2])

                    for column, sourceColumn, perm in synapses:
                        if column in onlyColumns:
                            if column not in synapsesByColumn:
                                synapsesByColumn[column] = []

                            syn = synapseTemplate.copy()
                            syn.update({
                                Keyword("src-col"): sourceColumn,
                                Keyword("perm"): perm,
                                Keyword("src-dt"): 0, # TODO don't assume this
                            })
                            synapsesByColumn[column].append(syn)

            ret = {}
            for column, synapses in synapsesByColumn.items():
                ret[(rgnId, lyrId, column)] = synapses
                responseChannel.put(ret)

        elif command == "get-inbits-cols":
            modelId, token, responseChannel = args
            modelData = self.journal[modelId]

            response = {
                Keyword("senses"): {},
                Keyword("regions"): {},
            }

            for senseName, senseData in modelData["senses"].items():
                response[Keyword("senses")][Keyword(senseName)] = {
                    Keyword("active-bits"): senseData["activeBits"],
                }

            for regionName, regionData in modelData["regions"].items():
                response[Keyword("regions")][Keyword(regionName)] = {}
                for layerName, layerData in regionData.items():
                    prevPredColumns = None
                    if modelId > 0:
                        prevModelData = self.journal[modelId - 1]
                        prevLayerData = prevModelData['regions'][regionName][layerName]
                        prevPredColumns = prevLayerData['predictedColumns']
                    response[Keyword("regions")][Keyword(regionName)][Keyword(layerName)] = {
                        Keyword("active-columns"): layerData["activeColumns"],
                        Keyword("pred-columns"): prevPredColumns
                    }

            responseChannel.put(response)

        elif command == "set-capture-options":
            captureOptions, = args
            self.captureOptions = captureOptions
        elif command == "register-viewport":
            viewport, responseChannel = args
            # Not actually used yet, but the client needs a token.
            responseChannel.put("this is your token")
        # else:
        #     print "Unrecognized command! %s" % command

    def getCellsSegmentsResponse(self, modelId, rgnId,
                                 lyrId, col, ci_si, layerData, segments,
                                 cellsPerColumn, nStimulusThresholdKey,
                                 nLearningThresholdKey):
        # TODO yes whole method is gross.
        firstCellInCol = col * cellsPerColumn
        activeCellsInCol = [cellId - firstCellInCol
                            for cellId in layerData["activeCells"]
                            if (cellId >= firstCellInCol and
                                cellId < firstCellInCol + cellsPerColumn)]
        predictedCellsInCol = []
        if modelId > 0:
            prevModelData = self.journal[modelId - 1]
            prevLayerData = prevModelData['regions'][str(rgnId)][str(lyrId)]
            predictedCellsInCol = [cellId - firstCellInCol
                                   for cellId in prevLayerData['predictedCells']
                                   if (cellId >= firstCellInCol and
                                       cellId < firstCellInCol + cellsPerColumn)]

        columnSegments = filter(lambda seg: (seg["column"] == col), segments)

        connectedActiveMax = -1
        cellWithMax = None
        segIdxWithMax = None
        ret = {}
        for i in range(cellsPerColumn):
            isActive = i in activeCellsInCol
            isPredicted = i in predictedCellsInCol

            cellState = None
            if isActive and isPredicted:
                cellState = "active-predicted"
            elif isActive:
                cellState = "active"
            elif isPredicted:
                cellState = "predicted"
            else:
                cellState = "inactive"

            cellData = {
                Keyword("cell-active?"): isActive,
                Keyword("cell-predictive?"): isPredicted,
                Keyword("cell-state"): Keyword(cellState),
            }

            segs = {}
            segIdx = -1 # HACK, it's gross that viz requires an index
            for segment in filter(lambda seg: seg["cell"] == i, columnSegments):
                segIdx += 1

                # TODO only send synapses according to viz-options
                # e.g. only for selected segment

                # This code would be a lot smaller without all the translation
                # to Keywords.
                retSynsByState = {}
                for sourcePath, synapsesByState in segment["synapses"].items():
                    synapseTemplate = {}
                    if sourcePath:
                        synapseTemplate[Keyword('src-id')] = Keyword(sourcePath[1])
                        if sourcePath[0] == 'regions':
                            synapseTemplate[Keyword('src-lyr')] = Keyword(sourcePath[2])

                    for state, synapses in synapsesByState.items():
                        syns = deque()
                        for targetCol, targetCell, perm in synapses:
                            syn = synapseTemplate.copy()
                            syn.update({
                                Keyword("src-col"): targetCol,
                                Keyword("perm"): perm,
                                Keyword("src-dt"): 1, # TODO don't assume this
                            })
                            syns.append(syn)
                        retSynsByState[Keyword(state)] = syns


                nConnectedActive = segment["nConnectedActive"]
                if nConnectedActive > connectedActiveMax:
                    connectedActiveMax = nConnectedActive
                    cellWithMax = i
                    segIdxWithMax = segIdx

                segData = {
                    Keyword("n-conn-act"): nConnectedActive,
                    Keyword("n-conn-tot"): segment["nConnectedTotal"],
                    Keyword("n-disc-act"): segment["nDisconnectedActive"],
                    Keyword("n-disc-tot"): segment["nDisconnectedTotal"],
                    Keyword("stimulus-th"): layerData[nStimulusThresholdKey],
                    Keyword("learning-th"): layerData[nLearningThresholdKey],
                    Keyword("syns-by-state"): retSynsByState,
                }
                segs[segIdx] = segData

            cellData[Keyword("segments")] = segs

            ret[i] = cellData

        selCell = None
        selSegIdx = None
        if ci_si is not None:
            selCell, selSegIdx = ci_si
        elif cellWithMax is not None and segIdxWithMax is not None:
            selCell = cellWithMax
            selSegIdx = segIdxWithMax

        if selCell is not None and selSegIdx is not None:
            ret[selCell][Keyword("selected-cell?")] = True
            # Because a client can select a segment and step backward and
            # forward in time, it may be requesting a segment that doesn't
            # exist in this timestep, or one that we've optimized away.
            if selSegIdx in ret[selCell][Keyword("segments")]:
                ret[selCell][Keyword("segments")][selSegIdx][Keyword("selected-seg?")] = True

        return ret
