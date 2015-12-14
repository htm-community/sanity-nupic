import os
import SimpleHTTPServer
import SocketServer
import signal
import sys
import threading
import webbrowser
import collections

from autobahn.twisted.websocket import WebSocketServerFactory
from twisted.internet import reactor
from twisted.python import log

import marshalling as marshal
from simulation import Simulation
from journal import Journal
from model import CLASanityModel
from websocket import makeSanityWebSocketClass

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- The above 3 meta tags *must* come first in the head; any other head content must come *after* these tags -->
  <title>NuPIC Runner - Sanity</title>

  <!-- Bootstrap -->
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.4/css/bootstrap.min.css">

  <!-- HTML5 shim and Respond.js for IE8 support of HTML5 elements and media queries -->
  <!-- WARNING: Respond.js doesn't work if you view the page via file:// -->
  <!--[if lt IE 9]>
    <script src="https://oss.maxcdn.com/html5shiv/3.7.2/html5shiv.min.js"></script>
    <script src="https://oss.maxcdn.com/respond/1.4.2/respond.min.js"></script>
  <![endif]-->

  <link rel="stylesheet" href="sanity/public/main.css">
</head>
<body>

  <!-- jQuery (necessary for Bootstrap's JavaScript plugins) -->
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.2/jquery.min.js"></script>
  <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.4/js/bootstrap.min.js"></script>

  <div id="sanity-app"></div>

  <script type="text/javascript" src="sanity/public/demos/out/goog/base.js"></script>
  <script type="text/javascript" src="sanity/public/demos/out/sanity.js"></script>
  <script type="text/javascript">goog.require("org.numenta.sanity.demos.runner");</script>
  <script type="text/javascript">
    org.numenta.sanity.demos.runner.init("NuPIC", "ws://localhost:%d", "capture", "drawing", "time-plots");
  </script>
</body>
</html>
"""

def makeRunnerRequestHandler(websocketPort):
    class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        def do_GET(self):
            filePath = self.path
            qpos = filePath.find('?')
            if qpos != -1:
                filePath = filePath[:qpos]

            if filePath == "/" or filePath == "/index.html":
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                content = PAGE % websocketPort
                self.wfile.write(content);
                self.wfile.close();
            else:
                curr = os.getcwd()
                rootFolder = os.path.dirname(__file__)
                os.chdir(rootFolder)
                SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)
                os.chdir(curr)

    return RequestHandler

class SanityRunner(object):
    def __init__(self, sanityModel, startSimThread=True):
        self.journal = Journal(sanityModel)
        self.simulation = Simulation(sanityModel, startSimThread)
        self.localTargets = {
            'simulation': marshal.channel(self.simulation),
            'journal': marshal.channel(self.journal),
        }

    def start(self, launchBrowser=True, useBackgroundThread=False):
        # Initialize the websocket, and gets its port
        factory = WebSocketServerFactory(debug=False)
        factory.protocol = makeSanityWebSocketClass(self.localTargets, {}, {})
        log.startLogging(sys.stdout)
        twistedData = reactor.listenTCP(0, factory)
        websocketPort = twistedData.socket.getsockname()[1]

        # Start the server that hosts the html / CSS / javascript
        server = SocketServer.TCPServer(("", 0),
                                        makeRunnerRequestHandler(websocketPort))
        serverThread = threading.Thread(target=server.serve_forever)
        serverThread.daemon = True
        serverThread.start()

        serverPort = server.socket.getsockname()[1]
        url = "http://localhost:%d/" % serverPort
        print "Navigate to %s" % url

        if launchBrowser:
            webbrowser.open(url)

        # Begin listening on the websocket
        if useBackgroundThread:
            t = threading.Thread(target=reactor.run, kwargs={"installSignalHandlers": 0})
            t.daemon = True
            t.start()
        else:
            reactor.run()

class CLASanityModelPatched(CLASanityModel):
    def __init__(self, model):
        super(CLASanityModelPatched, self).__init__(model)
        self.lastInput = ""

    def step(self):
        assert False

    def getInputDisplayText(self):
        # Hard to solve this general problem. Sometimes the v contains
        # unserializable datetimes.
        ret = []
        if isinstance(self.lastInput, collections.Mapping):
            for k, v in self.lastInput.items():
                ret.append((str(k), str(v)))

        return ret

def patchCLAModel(model):
    sanityModel = CLASanityModelPatched(model)
    runner = SanityRunner(sanityModel, startSimThread=False)
    runner.start(useBackgroundThread=True)
    simulation = runner.simulation
    runMethod = model.run
    def myRun(v):
        while True:
            if simulation.nStepsQueued > 0:
                shouldGo = True
            else:
                shouldGo = simulation.isGoing

            if shouldGo:
                ret = runMethod(v)
                sanityModel.lastInput = v
                sanityModel.onStepped()
                return ret
            else:
                # Having a timeout makes it receptive to ctrl+c...
                simulation.checkStatusEvent.wait(999999)
                simulation.checkStatusEvent.clear()

    model.run = myRun
