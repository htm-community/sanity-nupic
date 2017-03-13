import csv

import numpy as np

from nupic.bindings.algorithms import ConnectionsEventHandler


class TimeSeriesLogger(object):
  def __init__(self, outStream):
    self.csvOut = csv.writer(outStream)


  def startLoggingSegmentGrowth(self, connections):
    connections.subscribe(SegmentLogger(self.csvOut).__disown__())


  def logColumnActivity(self, tm, activeColumns):

    predictedColumns = np.unique(tm.getPredictiveCells() / tm.getCellsPerColumn())
    predictedActiveColumns = np.intersect1d(activeColumns, predictedColumns)
    burstingColumns = np.setdiff1d(activeColumns, predictedActiveColumns)
    predictedInactiveColumns = np.setdiff1d(predictedColumns, activeColumns)

    self.csvOut.writerow(("columnActivity", predictedActiveColumns.size,
                          burstingColumns.size, predictedInactiveColumns.size))


  def logSegmentActivity(self, tm, activeColumnsDense):
    activeSegments = tm.getActiveSegments()
    matchingSegments = np.setdiff1d(tm.getMatchingSegments(), activeSegments)

    (correctActiveSegments,
     incorrectActiveSegments) = _getSegmentAccuracy(activeSegments,
                                                    tm, activeColumnsDense)
    (correctMatchingSegments,
     incorrectMatchingSegments) = _getSegmentAccuracy(matchingSegments,
                                                      tm, activeColumnsDense)

    if correctActiveSegments.size > 0:
      self.csvOut.writerow(["correctActiveSegments"] +
                           correctActiveSegments.tolist())

    if incorrectActiveSegments.size > 0:
      self.csvOut.writerow(["incorrectActiveSegments"] +
                           incorrectActiveSegments.tolist())

    if correctMatchingSegments.size > 0:
      self.csvOut.writerow(["correctMatchingSegments"] +
                           correctMatchingSegments.tolist())

    if incorrectMatchingSegments.size > 0:
      self.csvOut.writerow(["incorrectMatchingSegments"] +
                           incorrectMatchingSegments.tolist())


  def logTimestep(self, t):
    self.csvOut.writerow(('t', t))



class SegmentLogger(ConnectionsEventHandler):

  def __init__(self, csvOut):
    super(SegmentLogger, self).__init__()
    self.csvOut = csvOut


  def onCreateSegment(self, segment):
    self.csvOut.writerow(("createSegment", segment))


  def onDestroySegment(self, segment):
    self.csvOut.writerow(("destroySegment", segment))



def _getSegmentAccuracy(segments, tm, activeColumnsDense):
  columnsForSegments = (tm.connections.mapSegmentsToCells(segments) /
                        tm.getCellsPerColumn())
  correctSegmentsMask = activeColumnsDense[columnsForSegments] != 0

  return segments[correctSegmentsMask], segments[~correctSegmentsMask]
