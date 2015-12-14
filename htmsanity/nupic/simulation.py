import threading

def simulationThread(simulation, checkEvent):
    while True:
        if simulation.nStepsQueued > 0:
            shouldGo = True
            simulation.nStepsQueued -= 1
        else:
            shouldGo = simulation.isGoing

        if shouldGo:
            ret = simulation.sanityModel.doStep()
            if ret is False:
                return
        else:
            checkEvent.wait()
            checkEvent.clear()

class Simulation(object):
    def __init__(self, sanityModel, startSimThread = True):
        self.sanityModel = sanityModel
        self.statusSubscribers = []
        self.isGoing = False
        self.nStepsQueued = 0
        self.checkStatusEvent = threading.Event()
        if startSimThread:
            self.simThread = threading.Thread(target = simulationThread,
                                              args = (self, self.checkStatusEvent))
            self.simThread.daemon = True
            self.simThread.start()

    def onStatusChanged(self):
        self.checkStatusEvent.set()
        for subscriber in self.statusSubscribers:
            subscriber.put([self.isGoing])

    def handleMessage(self, msg):
        command = msg[0]
        args = msg[1:]
        if command == "connect":
            pass
        elif command == "run":
            self.isGoing = True
            self.onStatusChanged()
        elif command == "pause":
            self.isGoing = False
            self.onStatusChanged()
        elif command == "toggle":
            self.isGoing = not self.isGoing
            self.onStatusChanged()
        elif command == "step":
            if not self.isGoing:
                self.nStepsQueued += 1
                self.checkStatusEvent.set()
        elif command == "subscribe-to-status":
            subscriberChannelMarshal, = args
            subscriberChannel = subscriberChannelMarshal.ch
            self.statusSubscribers.append(subscriberChannel)
            subscriberChannel.put([self.isGoing])
        else:
            print "Unrecognized command! %s" % command

    # Act like a channel.
    def put(self, v):
        self.handleMessage(v)
