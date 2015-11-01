import threading

def simulationThread(simulation, checkEvent):
    while True:
        while simulation.isGoing:
            simulation.step()
        checkEvent.wait()
        checkEvent.clear()

class Simulation(object):
    def __init__(self, journal, stepfn):
        self.journal = journal
        self.statusSubscribers = []
        self.isGoing = False
        self.stepfn = stepfn
        self.checkStatusEvent = threading.Event()
        self.simThread = threading.Thread(target = simulationThread,
                                          args = (self, self.checkStatusEvent))
        self.simThread.daemon = True
        self.simThread.start()

    def onStatusChanged(self):
        self.checkStatusEvent.set()
        for subscriber in self.statusSubscribers:
            subscriber.put([self.isGoing])

    def step(self):
        model, displayValue = self.stepfn()
        self.journal.append(model, displayValue)

    def handleMessage(self, msg):
        command = str(msg[0])
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
                self.step()
        elif command == "subscribe-to-status":
            subscriberChannel, = args
            self.statusSubscribers.append(subscriberChannel)
            subscriberChannel.put([self.isGoing])
        else:
            print "Unrecognized command! %s" % command
