from collections import deque
import numpy
from autobahn.twisted.websocket import WebSocketServerProtocol
from transit.writer import Writer
from transit.reader import Reader
from transit.transit_types import Keyword
from transit.write_handlers import IntHandler, FloatHandler, ArrayHandler
from StringIO import StringIO
from twisted.internet import reactor

import marshalling as marshal

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

# twisted wants a class, not an object. We need to give the object
# parameters of our own. So we use a closure.
def makeSanityWebSocketClass(localTargets):
    class SanityWebSocket(WebSocketServerProtocol):
        def sanitySend(self, message):
            writeHandlers = marshal.getWriteHandlers(localTargets, {})
            writeHandlers.update({
                deque: ArrayHandler,
                numpy.uint32: NumpyIntHandler,
                numpy.float32: NumpyFloatHandler,
                numpy.ndarray: NumpyArrayHandler,
            })
            io = StringIO()
            writer = Writer(io, "json")
            for objType, handler in writeHandlers.items():
                writer.register(objType, handler)
            writer.write(message)
            serialized = str(io.getvalue())
            reactor.callFromThread(WebSocketServerProtocol.sendMessage,
                                   self, serialized, isBinary=False)

        def onConnect(self, request):
            print("Client connecting: {0}".format(request.peer))

        def onOpen(self):
            print("WebSocket connection open.")

        def onMessage(self, payload, isBinary):
            if isBinary:
                print("Binary message received: {0} bytes".format(len(payload)))
            else:
                readHandlers = marshal.getReadHandlers(
                    localTargets,
                    lambda targetId, v: self.sanitySend((targetId, Keyword('put!'), v)),
                    lambda targetId: self.sanitySend((targetId, Keyword('close!'))),
                    {}
                )
                reader = Reader("json")
                for tag, handler in readHandlers.items():
                    reader.register(tag, handler)
                msg = reader.read(StringIO(payload))
                targetId, cmd, val = msg
                cmdStr = str(cmd)
                if cmdStr == 'put!' or cmdStr == 'close!':
                    if targetId in localTargets:
                        ch = localTargets[targetId].ch
                        if cmdStr == 'put!':
                            ch.put(val)
                        elif cmdStr == 'close!':
                            ch.close()
                    else:
                        print "Unrecognized target! " + target
                else:
                    print "Unrecognized command! " + cmdStr

        def onClose(self, wasClean, code, reason):
            print("WebSocket connection closed: {0}".format(reason))

    return SanityWebSocket
