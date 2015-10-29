from autobahn.twisted.websocket import WebSocketServerProtocol
from transit.writer import Writer
from transit.reader import Reader
from transit.transit_types import Keyword
from StringIO import StringIO

def toTransitStr(v):
    io = StringIO()
    writer = Writer(io, "json")
    writer.write(v)
    return str(io.getvalue())

class WebSocketChannelProxy(object):
    def __init__(self, target, websocket):
        self.target = target
        self.websocket = websocket

    def close(self):
        m = [self.target, Keyword("put!")]
        serialized = toTransitStr(m)
        self.websocket.sendMessage(serialized, False)

    def put(self,msg):
        m = [self.target, Keyword("put!"), msg]
        serialized = toTransitStr(m)
        self.websocket.sendMessage(serialized, False)

def channelProxyHandler(websocket):
    class ChannelProxyHandler(object):
        @staticmethod
        def from_rep(v):
            channel_proxy = WebSocketChannelProxy(v, websocket)
            return channel_proxy

    return ChannelProxyHandler

def runnerWebSocketProtocol(localTargets):
    class RunnerWebSocket(WebSocketServerProtocol):
        def onConnect(self, request):
            print("Client connecting: {0}".format(request.peer))

        def onOpen(self):
            print("WebSocket connection open.")

        def onMessage(self, payload, isBinary):
            if isBinary:
                print("Binary message received: {0} bytes".format(len(payload)))
            else:
                reader = Reader("json")
                reader.register("ChannelProxy", channelProxyHandler(self))
                msg = reader.read(StringIO(payload))

                target, cmd, val = msg
                assert str(cmd) == "put!"
                if target in localTargets:
                    localTargets[target](val)
                else:
                    print "Unrecognized target! " + target

        def onClose(self, wasClean, code, reason):
            print("WebSocket connection closed: {0}".format(reason))

    return RunnerWebSocket
