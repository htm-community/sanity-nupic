from collections import deque
import numpy
from autobahn.twisted.websocket import WebSocketServerProtocol
from transit.writer import Writer
from transit.reader import Reader
from transit.transit_types import Keyword
from transit.write_handlers import IntHandler, FloatHandler, ArrayHandler
from StringIO import StringIO
from twisted.internet import reactor

class NumpyIntHandler(IntHandler):
    @staticmethod
    def rep(i):
        return int(i)

class NumpyFloatHandler(FloatHandler):
    @staticmethod
    def rep(f):
        return float(f)

class NumpyArrayHandler(ArrayHandler):
    @staticmethod
    def rep(a):
        return a.tolist()

def toTransitStr(v):
    io = StringIO()
    writer = Writer(io, "json")
    writer.register(deque, ArrayHandler)
    writer.register(numpy.uint32, NumpyIntHandler)
    writer.register(numpy.float32, NumpyFloatHandler)
    writer.register(numpy.ndarray, NumpyArrayHandler)
    writer.write(v)
    return str(io.getvalue())

class WebSocketChannelProxy(object):
    def __init__(self, target, websocket):
        self.target = target
        self.websocket = websocket

    def close(self):
        m = [self.target, Keyword("put!")]
        serialized = toTransitStr(m)
        reactor.callFromThread(WebSocketServerProtocol.sendMessage,
                               self.websocket, serialized, False)

    def put(self,msg):
        m = [self.target, Keyword("put!"), msg]
        serialized = toTransitStr(m)
        reactor.callFromThread(WebSocketServerProtocol.sendMessage,
                               self.websocket, serialized, False)

class WebSocketChannelProxyHandler(object):
    def __init__(self, websocket):
        self.websocket = websocket

    def from_rep(self, v):
        return WebSocketChannelProxy(v, self.websocket)

# twisted wants a class, not an object. We need to give the object
# parameters of our own. So we use a closure.
def makeVizWebSocketClass(localTargets):
    class VizWebSocket(WebSocketServerProtocol):
        def onConnect(self, request):
            print("Client connecting: {0}".format(request.peer))

        def onOpen(self):
            print("WebSocket connection open.")

        def onMessage(self, payload, isBinary):
            if isBinary:
                print("Binary message received: {0} bytes".format(len(payload)))
            else:
                reader = Reader("json")
                reader.register("ChannelProxy", WebSocketChannelProxyHandler(self))
                msg = reader.read(StringIO(payload))

                target, cmd, val = msg
                assert str(cmd) == "put!"
                if target in localTargets:
                    localTargets[target](val)
                else:
                    print "Unrecognized target! " + target

        def onClose(self, wasClean, code, reason):
            print("WebSocket connection closed: {0}".format(reason))

    return VizWebSocket
