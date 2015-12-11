import os
import SimpleHTTPServer
import SocketServer
import sys
import threading
import webbrowser

from autobahn.twisted.websocket import WebSocketServerFactory
from twisted.internet import reactor
from twisted.python import log

import marshalling as marshal
from simulation import Simulation
from journal import Journal
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
                SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    return RequestHandler

class SanityRunner(object):
    def __init__(self, sanityModel):
        journal = Journal(sanityModel)
        simulation = Simulation(sanityModel)
        self.localTargets = {
            'simulation': marshal.channel(simulation),
            'journal': marshal.channel(journal),
        }

    def start(self, launchBrowser=True, useBackgroundThread=False):
        # Initialize the websocket, and gets its port
        factory = WebSocketServerFactory(debug=False)
        factory.protocol = makeSanityWebSocketClass(self.localTargets, {}, {})
        log.startLogging(sys.stdout)
        twistedData = reactor.listenTCP(0, factory)
        websocketPort = twistedData.socket.getsockname()[1]

        # Start the server that hosts the html / CSS / javascript
        rootFolder = os.path.dirname(__file__)
        os.chdir(rootFolder)
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
