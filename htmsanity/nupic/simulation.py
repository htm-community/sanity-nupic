import threading

def simulationThread(simulation, checkEvent):
    while True:
        while simulation.isGoing:
            ret = simulation.sanityModel.doStep()
            if ret is False:
                return
        checkEvent.wait()
        checkEvent.clear()

class Simulation(object):
    def __init__(self, sanityModel):
        self.sanityModel = sanityModel
        self.statusSubscribers = []
        self.isGoing = False
        self.checkStatusEvent = threading.Event()
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
                self.sanityModel.doStep()
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
