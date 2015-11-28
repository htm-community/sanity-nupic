import uuid

##
## For message senders / receivers
##

class ChannelMarshal(object):
  def __init__(self, ch, useOnce):
    self.ch = ch
    self.useOnce = useOnce
    self.isReleased = False

    self._lastEventIds = {
      'didRelease': 0,
    }
    self._listeners = {
      'didRelease': {},
    }

  def addEventListener(self, event, fn):
    eventId = self.lastEventIds[event] + 1
    self._listeners[event][eventId] = fn
    self._lastEventIds[event] = eventId

  def removeEventListener(self, event, eventId):
    del self._listeners[event][eventId]

  def release(self):
    assert not self.isReleased
    self.isReleased = True
    for fn in self._listeners['didRelease'].values():
      fn()

def channel(ch, useOnce=False):
  """Returns a ChannelMarshal. It can then carry a channel across the network.

  When Client A serializes a ChannelMarshal, Client A will assign it a targetId
  and send the targetId across the network. When decoding the message, Client B
  will set the decoded ChannelMarshal's ch to a ChannelProxy. Any `put` or
  `close` on a ChannelProxy will be delivered across the network back to Client
  A.

  Client B should not send a ChannelMarshal back to Client A. It will create a
  silly chain of proxies. Use `channelWeak`.

  All of this assumes that the network code on both clients is using
  write-handlers and read-handlers that follow this protocol.

  """
  return ChannelMarshal(ch, useOnce)

class ChannelWeakMarshal(object):
  def __init__(self, targetId):
    self.targetId = targetId

def channelWeak(targetId):
  """Returns a ChannelWeakMarshal. It allows a marshalled channel to be referred
  to without creating chains of proxies.

  When a client decodes a message containing a ChannelWeakMarshal, it will check
  if this targetId belongs to this client. If it does, this ChannelWeakMarshal
  will be 'decoded' into its original ChannelMarshal. This allows Client B to
  tell Client A 'If we get disconnected, send me this data blob on reconnect,
  and I'll remember you'. This allows the data blob to contain channels that are
  usable again on second send without causing a chain of proxies.

  All of this assumes that the network code on both clients is using
  write-handlers and read-handlers that follow this protocol.

  """
  return ChannelWeakMarshal(targetId)

##
## For networking
##

class ChannelProxy(object):
  def __init__(self, targetId, fput, fclose):
    self.targetId = targetId
    self.fput = fput
    self.fclose = fclose

  def put(self, msg):
    self.fput(self.targetId, msg)

  def close(self):
    self.fclose(self.targetId)

class ChannelMarshalReadHandler(object):
  def __init__(self, fput, fclose):
    self.fput = fput
    self.fclose = fclose

  def from_rep(self, v):
    return channel(ChannelProxy(v, self.fput, self.fclose))

class ChannelMarshalWriteHandler(object):
  def __init__(self, localTargets):
    self.localTargets = localTargets

  @staticmethod
  def tag(channelMarshal):
    return 'ChannelMarshal'

  def rep(self, channelMarshal):
    assert not channelMarshal.isReleased
    targetId = uuid.uuid1()
    self.localTargets[targetId] = channelMarshal
    channelMarshal.addEventListener(
      'didRelease', lambda: self.localTargets.pop(targetId)
    )

    return targetId

class ChannelWeakMarshalReadHandler(object):
  def __init__(self, localTargets):
    self.localTargets = localTargets

  def from_rep(self, targetId):
    return self.localTargets.get(targetId, ChannelWeakMarshal(targetId))

class ChannelWeakMarshalWriteHandler(object):
  @staticmethod
  def tag(channelWeakMarshal):
    return 'ChannelWeakMarshal'

  @staticmethod
  def rep(channelWeakMarshal):
    return channelWeakMarshal.targetId

def getReadHandlers(localTargets, fput, fclose, remoteResources):
  return {
    'ChannelMarshal': ChannelMarshalReadHandler(fput, fclose),
    'ChannelWeakMarshal': ChannelWeakMarshalReadHandler(localTargets),
  }

def getWriteHandlers(localTargets, localResources):
  return {
    ChannelMarshal: ChannelMarshalWriteHandler(localTargets),
    ChannelWeakMarshal: ChannelWeakMarshalWriteHandler,
  }
