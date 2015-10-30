import datetime

class Simulation(object):
    def __init__(self, model, journal, inputIter):
        self.model = model
        self.journal = journal
        self.inputIter = inputIter
        self.statusSubscribers = []
        self.isGoing = False

    def pushStatusToSubscribers(self):
        for subscriber in self.statusSubscribers:
            subscriber.put([self.isGoing])

    def handleMessage(self, msg):
        command = str(msg[0])
        args = msg[1:]
        if command == "connect":
            pass
        elif command == "run":
            self.isGoing = True
            self.pushStatusToSubscribers()
        elif command == "pause":
            self.isGoing = False
            self.pushStatusToSubscribers()
        elif command == "toggle":
            self.isGoing = not self.isGoing
            self.pushStatusToSubscribers()
        elif command == "step":
            timestampStr, consumptionStr = self.inputIter.next()
            self.model.run({
                "timestamp": datetime.datetime.strptime(timestampStr, "%m/%d/%y %H:%M"),
                "kw_energy_consumption": float(consumptionStr),
            })
            self.journal.append(self.model)
        elif command == "subscribe-to-status":
            subscriberChannel, = args
            self.statusSubscribers.append(subscriberChannel)
            subscriberChannel.put(self.isGoing)
        else:
            print "Unrecognized command! %s" % command
