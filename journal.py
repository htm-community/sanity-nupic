import numpy
from collections import deque
from nupic.bindings.math import GetNTAReal
from transit.transit_types import Keyword

def getBitStates(model):
    spRegion = model._getSPRegion().getSelf()
    spOutput = spRegion._spatialPoolerOutput
    tp = model._getTPRegion().getSelf()._tfdr
    npPredictedCells = tp.getPredictedState().reshape(-1).nonzero()[0]

    return {
        "activeBits": spRegion._spatialPoolerInput.nonzero()[0].tolist(),
        "activeColumns": spOutput.nonzero()[0].tolist(),
        "activeCells": tp.getActiveState().nonzero()[0].tolist(),
        "predictedCells": npPredictedCells.tolist(),
        "predictedColumns": numpy.unique(npPredictedCells / tp.cellsPerColumn).tolist(),
    }

def getProximalSynapses(model, onlyBits, onlyConnected=True):
    proximalSynapses = deque()
    spRegion = model._getSPRegion().getSelf()
    sp = spRegion._sfdr
    tpRegion = model._getTPRegion()
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

def getDistalSegments(model, columnsToCheck, onlyTargets, onlyConnected=True):
    spRegion = model._getSPRegion().getSelf()
    sp = spRegion._sfdr
    tp = model._getTPRegion().getSelf()._tfdr

    distalSegments = deque()

    for col in columnsToCheck:
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
                    "nLearningThreshold": tp.minThreshold, # TODO don't do per-segment
                    "nStimulusThreshold": tp.activationThreshold, # TODO don't do per-segment
                })

    return distalSegments

def makeStep(model, modelId):
    return {
        Keyword("model-id"): modelId,
        Keyword("timestep"): modelId, # hack
    }

class Journal(object):
    def __init__(self, model):
        self.journal = []
        self.subscribers = []
        self.nextModelId = 0

        sp = model._getSPRegion().getSelf()._sfdr
        self.inputDimensions = sp.getInputDimensions()
        self.columnDimensions = sp.getColumnDimensions()

        self.cellsPerColumn = model._getTPRegion().getSelf()._tfdr.cellsPerColumn

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

    def append(self, model, displayValue=None):
        modelData = getBitStates(model)

        # TODO: grab the specified synapse types

        if self.captureOptions[Keyword("ff-synapses")][Keyword("capture?")]:
            modelData["proximalSynapses"] = getProximalSynapses(model, modelData["activeBits"])
        else:
            modelData["proximalSynapses"] = []
        if len(self.journal) > 0 and \
           self.captureOptions[Keyword("distal-synapses")][Keyword("capture?")]:

            prevActiveCells = self.journal[-1]["activeCells"]
            prevPredictedColumns = self.journal[-1]["predictedColumns"]
            columnsToCheck = modelData["activeColumns"] + prevPredictedColumns
            modelData["distalSegments"] = getDistalSegments(model, columnsToCheck, prevActiveCells)
        else:
            modelData["distalSegments"] = []
        self.journal.append(modelData)

        # TODO: only keep nKeepSteps models

        step = makeStep(model, self.nextModelId)
        self.nextModelId += 1

        if displayValue:
            step[Keyword("display-value")] = displayValue

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

            stepTemplate = {
                Keyword("senses"): {
                    Keyword("concatenated"): {
                        Keyword("dimensions"): self.inputDimensions,
                    },
                },
                Keyword("regions"): {
                    Keyword("rgn-0"): {
                        Keyword("layer-3"): {
                            Keyword("dimensions"): self.columnDimensions,
                        },
                    },
                },
            }

            responseChannel.put([stepTemplate, self.captureOptions])
        elif command == "get-cells-segments":
            modelId, rgnId, lyrId, col, ci_si, token, responseChannel = args

            cell = None
            segIdx = None
            if ci_si:
                cell, segIdx = ci_si

            modelData = self.journal[modelId]

            lower = col * self.cellsPerColumn
            upper = (col + 1) * self.cellsPerColumn

            ac = filter(lambda x: (x >= lower and x < upper), modelData["activeCells"])
            pc = []
            if modelId > 0:
                pc = filter(lambda x: (x >= lower and x < upper),
                            self.journal[modelId - 1]["predictedCells"])
            ret = {}

            colSegs = filter(lambda x: (x["column"] == col),
                             modelData["distalSegments"])

            connectedActiveMax = -1
            cellWithMax = None
            segIdxWithMax = None

            for i in range(self.cellsPerColumn):
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
                for seg in filter(lambda x: (x["cell"] == i),
                                  colSegs):
                    segIdx += 1

                    # TODO only send synapses according to viz-options
                    # e.g. only for selected segment
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
                        Keyword("stimulus-th"): seg["nStimulusThreshold"],
                        Keyword("learning-th"): seg["nLearningThreshold"],
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
            proximalSynapses = modelData["proximalSynapses"]
            activeBits = modelData["activeBits"]

            synapsesByColumn = {}

            for column, inputBit, perm in proximalSynapses:
                if column in onlyColumns and inputBit in activeBits:
                    if column not in synapsesByColumn:
                        synapsesByColumn[column] = []
                    synapsesByColumn[column].append({
                        Keyword("src-id"): Keyword("concatenated"),
                        Keyword("src-col"): inputBit,
                        Keyword("syn-state"): Keyword("active"),
                        Keyword("perm"): perm,
                    })

            ret = {}
            for column, synapses in synapsesByColumn.items():
                ret[(Keyword("rgn-0"), Keyword("layer-3"), column)] = synapses
                responseChannel.put(ret)

        elif command == "get-inbits-cols":
            modelId, token, responseChannel = args
            modelData = self.journal[modelId]

            predColumns = None
            if modelId > 0:
                predColumns = self.journal[modelId - 1]["predictedColumns"]

            responseChannel.put({
                Keyword("senses"): {
                    Keyword("concatenated"): {
                        Keyword("active-bits"): modelData["activeBits"],
                    },
                },
                Keyword("regions"): {
                    Keyword("rgn-0"): {
                        Keyword("layer-3"): {
                            Keyword("active-columns"): modelData["activeColumns"],
                            Keyword("pred-columns"): predColumns,
                        },
                    },
                },
            })
        elif command == "set-capture-options":
            captureOptions, = args
            self.captureOptions = captureOptions
        elif command == "register-viewport":
            viewport, responseChannel = args
            # Not actually used yet, but the client needs a token.
            responseChannel.put("this is your token")
        # else:
        #     print "Unrecognized command! %s" % command
