import datetime

class Simulation(object):
    def __init__(self, model, journal, inputIter):
        self.model = model
        self.journal = journal
        self.inputIter = inputIter

    def handleMessage(self, msg):
        command = str(msg[0])
        if command == "connect":
            print "connect!"
        elif command == "step":
            timestampStr, consumptionStr = self.inputIter.next()
            self.model.run({
                "timestamp": datetime.datetime.strptime(timestampStr, "%m/%d/%y %H:%M"),
                "kw_energy_consumption": float(consumptionStr),
            })

            self.journal.append(self.model)

        else:
            print "Unrecognized command! %s" % command
