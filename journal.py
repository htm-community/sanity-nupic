from transit.transit_types import Keyword

def makeStep(vizModel, modelId):
    return {
        Keyword("model-id"): modelId,
        Keyword("timestep"): vizModel.timestep,
    }

class Journal(object):
    def __init__(self, vizModel):
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
        }

        self.absorbStepTemplate(vizModel)
        self.append(vizModel)
        vizModel.addEventListener('didStep', lambda: self.append(vizModel))

    def absorbStepTemplate(self, vizModel):
        self.stepTemplate = vizModel.query(networkLayout=True)
        senses = {}
        for name, senseData in self.stepTemplate["senses"].items():
            senses[Keyword(name)] = {
                Keyword("dimensions"): senseData["dimensions"],
            }

        regions = {}
        for regionName, regionData in self.stepTemplate["regions"].items():
            region = {}
            for layerName, layerData in regionData.items():
                region[Keyword(layerName)] = {
                    Keyword("dimensions"): layerData["dimensions"],
                }
            regions[Keyword(regionName)] = region

        self.stepTemplateEncoded = {
            Keyword("senses"): senses,
            Keyword("regions"): regions,
        }

    def append(self, vizModel):
        queryArgs = {
            'bitStates': True,
        }

        if self.captureOptions[Keyword("ff-synapses")][Keyword("capture?")]:
            proximalSynapsesQuery = {
                'onlyActive': True,
                'onlyConnected': True,
            }
            queryArgs.update({
                'proximalSynapses': True,
                'proximalSynapsesQuery': {
                    'onlyActive': True,
                    'onlyConnected': True,
                },
            })

        if (len(self.journal) > 0 and
            self.captureOptions[Keyword("distal-synapses")][Keyword("capture?")]):

            distalSegmentsQuery = {
                'senses': {},
                'regions': {},
            }

            for senseName, prevSenseData in self.journal[-1]['senses'].items():
                distalSegmentsQuery['senses'][senseName] = {
                    'targets': prevSenseData['activeBits'],
                }

            for regionName, prevRegionData in self.journal[-1]['regions'].items():
                distalSegmentsQuery['regions'][regionName] = {}
                for layerName, prevLayerData in prevRegionData.items():
                    distalSegmentsQuery['regions'][regionName][layerName] = {
                        'targets': prevLayerData['activeCells'],
                        'additionalColumns': prevLayerData['predictedColumns'],
                    }

            queryArgs.update({
                'distalSegments': True,
                'distalSegmentsQuery': distalSegmentsQuery,
            })

        # TODO: grab the specified synapse types

        self.journal.append(vizModel.query(**queryArgs))

        # TODO: only keep nKeepSteps models

        step = makeStep(vizModel, self.nextModelId)
        self.nextModelId += 1

        step[Keyword("display-value")] = vizModel.getInputDisplayText()

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

            cell = None
            segIdx = None
            if ci_si:
                cell, segIdx = ci_si

            modelData = self.journal[modelId]
            layerData = modelData['regions'][str(rgnId)][str(lyrId)]
            cellsPerColumn = self.stepTemplate['regions'][str(rgnId)][str(lyrId)]['cellsPerColumn']

            lower = col * cellsPerColumn
            upper = (col + 1) * cellsPerColumn

            ac = filter(lambda x: (x >= lower and x < upper), layerData["activeCells"])
            pc = []
            if modelId > 0:
                prevModelData = self.journal[modelId - 1]
                prevLayerData = prevModelData['regions'][str(rgnId)][str(lyrId)]
                pc = filter(lambda x: (x >= lower and x < upper),
                            prevLayerData['predictedCells'])

            ret = {}

            colSegs = filter(lambda x: (x["column"] == col),
                             layerData.get("distalSegments", []))

            connectedActiveMax = -1
            cellWithMax = None
            segIdxWithMax = None

            for i in range(cellsPerColumn):
                isActive = (i + lower) in ac
                isPredicted = (i + lower) in pc
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
                for seg in filter(lambda x: (x["cell"] == i), colSegs):
                    segIdx += 1

                    # TODO only send synapses according to viz-options
                    # e.g. only for selected segment

                    # TODO this is still not ready for hierarchy
                    activeSynapses = []
                    for targetCol, targetCell, perm in seg["synapses"]:
                        activeSynapses.append({
                            Keyword("src-col"): targetCol,
                            Keyword("src-id"): Keyword("rgn-0"),
                            Keyword("src-lyr"): Keyword("layer-3"),
                            Keyword("perm"): perm,
                        })

                    nConnectedActive = seg["nConnectedActive"]
                    if nConnectedActive > connectedActiveMax:
                        connectedActiveMax = nConnectedActive
                        cellWithMax = i
                        segIdxWithMax = segIdx

                    segData = {
                        Keyword("n-conn-act"): nConnectedActive,
                        Keyword("n-conn-tot"): seg["nConnectedTotal"],
                        Keyword("n-disc-act"): seg["nDisconnectedActive"],
                        Keyword("n-disc-tot"): seg["nDisconnectedTotal"],
                        Keyword("stimulus-th"): layerData["nDistalStimulusThreshold"],
                        Keyword("learning-th"): layerData["nDistalLearningThreshold"],
                        Keyword("syns-by-state"): {
                            Keyword("active"): activeSynapses,
                        },
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

            responseChannel.put({
                Keyword("distal"): ret,
            })

        elif command == "get-ff-in-synapses":
            modelId, rgnId, lyrId, onlyColumns, token, responseChannel = args
            modelData = self.journal[modelId]
            layerData = modelData["regions"][str(rgnId)][str(lyrId)]
            proximalSynapses = layerData.get('proximalSynapses', [])

            synapsesByColumn = {}

            for sourcePath, synapses in proximalSynapses.items():
                synapseTemplate = {}
                activeBits = []
                if sourcePath:
                    synapseTemplate[Keyword('src-id')] = Keyword(sourcePath[1])
                    if sourcePath[0] == 'senses':
                        senseData = modelData['senses'][sourcePath[1]]
                        activeBits = senseData['activeBits']
                    elif sourcePath[0] == 'regions':
                        synapseTemplate[Keyword('src-lyr')] = Keyword(sourcePath[2])
                        sourceLayerData = modelData['regions'][sourcePath[1]][sourcePath[2]]
                        activeBits = sourceLayerData['activeCells']

                for column, inputBit, perm in synapses:
                    if column in onlyColumns and inputBit in activeBits:
                        if column not in synapsesByColumn:
                            synapsesByColumn[column] = []

                        syn = synapseTemplate.copy()
                        syn.update({
                            Keyword("src-col"): inputBit,
                            Keyword("syn-state"): Keyword("active"),
                            Keyword("perm"): perm,
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
