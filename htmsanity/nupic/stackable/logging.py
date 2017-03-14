import csv
import io

import numpy as np

from nupic.bindings.algorithms import ConnectionsEventHandler


class TimeSeriesLogger(object):
  def __init__(self, outStream=None):
    if outStream is None:
      self.textOut = io.BytesIO()
      outStream = self.textOut
    else:
      self.textOut = None

    self.csvOut = csv.writer(outStream)

    self.timestep = 0


  def extract(self):
    if self.textOut is None:
      raise AssertionError("Don't use extract if you're supplying your own outStream.")

    return self.textOut.getvalue()


  def startLoggingSegmentGrowth(self, connections):
    connections.subscribe(SegmentLogger(self.csvOut).__disown__())


  def logColumnActivity(self, tm, activeColumns):

    predictedColumns = np.unique(tm.getPredictiveCells() / tm.getCellsPerColumn())
    predictedActiveColumns = np.intersect1d(activeColumns, predictedColumns)
    burstingColumns = np.setdiff1d(activeColumns, predictedActiveColumns)
    predictedInactiveColumns = np.setdiff1d(predictedColumns, activeColumns)

    self.csvOut.writerow(("columnActivity", predictedActiveColumns.size,
                          burstingColumns.size, predictedInactiveColumns.size))


  def logSegmentActivity(self, tm, activeColumns):
    activeSegments = tm.getActiveSegments()
    matchingSegments = np.setdiff1d(tm.getMatchingSegments(), activeSegments)

    (correctActiveSegments,
     incorrectActiveSegments) = _getSegmentAccuracy(activeSegments,
                                                    tm, activeColumns)
    (correctMatchingSegments,
     incorrectMatchingSegments) = _getSegmentAccuracy(matchingSegments,
                                                      tm, activeColumns)

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


  def logTimestep(self):
    self.csvOut.writerow(('t', self.timestep))
    self.timestep += 1



class SegmentLogger(ConnectionsEventHandler):

  def __init__(self, csvOut):
    super(SegmentLogger, self).__init__()
    self.csvOut = csvOut


  def onCreateSegment(self, segment):
    self.csvOut.writerow(("createSegment", segment))


  def onDestroySegment(self, segment):
    self.csvOut.writerow(("destroySegment", segment))



def _getSegmentAccuracy(segments, tm, activeColumns):
  columnsForSegments = (tm.connections.mapSegmentsToCells(segments) /
                        tm.getCellsPerColumn())
  correctSegmentsMask = np.in1d(columnsForSegments, activeColumns)

  return segments[correctSegmentsMask], segments[~correctSegmentsMask]
