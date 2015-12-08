import uuid

class Releasable(object):
  def __init__(self):
    self.isReleased = False

    self._lastEventIds = {
      'didRelease': 0,
    }
    self._listeners = {
      'didRelease': {},
    }

  def addEventListener(self, event, fn):
    eventId = self._lastEventIds[event] + 1
    self._listeners[event][eventId] = fn
    self._lastEventIds[event] = eventId

  def removeEventListener(self, event, eventId):
    del self._listeners[event][eventId]

  def release(self):
    assert not self.isReleased
    self.isReleased = True
    for fn in self._listeners['didRelease'].values():
      fn()


##
## For message senders / receivers
##

class ChannelMarshal(Releasable):
  def __init__(self, ch, useOnce):
    super(ChannelMarshal, self).__init__()
    self.ch = ch
    self.useOnce = useOnce

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

class BigValueMarshal(Releasable):
  def __init__(self, resourceId, value):
    super(BigValueMarshal, self).__init__()
    self.resourceId = resourceId
    self.value = value

def bigValue(value):
  """Returns a BigValueMarshal. It puts this value in a box labeled 'recipients
  should cache this so that I don't have to send it every time.'

  When Client B decodes a message containing a BigValueMarshal, it will save the
  value and tell Client A that it has saved the value. Later, when Client A
  serializes the same BigValueMarshal to send it to Client B, it will only
  include the resourceId, and Client B will reinsert the value when it decodes
  the message.

  Call `release` on a BigValueMarshal to tell other machines that they can
  release it.

  All of this assumes that the network code on both clients is using
  write-handlers and read-handlers that follow this protocol.

  """
  return BigValueMarshal(uuid.uuid1(), value)

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

class OnRemoteResourceReleased(object):
  def __init__(self, remoteResources, resourceId):
    self.remoteResources = remoteResources
    self.resourceId = resourceId

  def put(self, msg):
    del self.remoteResources[self.resourceId]

class BigValueMarshalReadHandler(object):
  def __init__(self, remoteResources):
    self.remoteResources = remoteResources

  def from_rep(self, m):
    resourceId = m['resource-id']
    onSavedChannelMarshal = m.get('on-saved-c-marshal', None)
    isNew = resourceId not in self.remoteResources
    if isNew:
      self.remoteResources[resourceId] = BigValueMarshal(resourceId, m['value'])

    if onSavedChannelMarshal is not None:
      # Depending on timing, this may happen multiple times for a single resource.
      # The other machine wants to free up this channel, so always respond.
      # But only give it an onReleased channel once.
      onReleaseChannelMarshal = None
      if isNew:
        onRelease = OnRemoteResourceReleased(self.remoteResources, resourceId)
        onReleaseChannelMarshal = channel(onRelease)
      msg = ['saved', onReleaseChannelMarshal]
      onSavedChannelMarshal.ch.put(msg)

    return self.remoteResources[resourceId]

class OnLocalResourceReleased(object):
  def __init__(self, localResources, resourceId):
    self.localResources = localResources
    self.resourceId = resourceId

  def put(self, _):
    entry = self.localResources[self.resourceId]
    del self.localResources[self.resourceId]

    ch = entry['onReleasedChannel']
    if ch is not None:
      ch.put(('released'))

class OnResourceSavedRemotely(object):
  def __init__(self, localResources, resourceId):
    self.localResources = localResources
    self.resourceId = resourceId

  def put(self, msg):
    cmd, onReleasedChannelMarshal = msg
    entry = self.localResources[self.resourceId]
    entry['isPushed'] = True
    if onReleasedChannelMarshal is not None:
      entry['onReleasedChannel'] = onReleasedChannelMarshal.ch

class BigValueMarshalWriteHandler(object):
  def __init__(self, localResources):
    self.localResources = localResources

  @staticmethod
  def tag(bigValueMarshal):
    return 'BigValueMarshal'

  def rep(self, bigValueMarshal):
    resourceId = bigValueMarshal.resourceId

    if resourceId in self.localResources:
      entry = self.localResources[resourceId]
    else:
      entry = {
        'marshal': bigValueMarshal,
        'isPushed': False,
        'onReleasedChannel': None,
      }
      if not bigValueMarshal.isReleased:
        self.localResources[resourceId] = entry
        onRelease = OnLocalResourceReleased(self.localResources, resourceId)
        bigValueMarshal.addEventListener('didRelease',
                                         lambda: onRelease.put('release'))

    if entry['isPushed']:
      return {
        'resource-id': resourceId,
      }
    else:
      onRemotelySaved = OnResourceSavedRemotely(self.localResources, resourceId)
      return {
        'resource-id': resourceId,
        'value': bigValueMarshal.value,
        'on-saved-c-marshal': channel(onRemotelySaved),
      }

def getReadHandlers(localTargets, fput, fclose, remoteResources):
  return {
    'ChannelMarshal': ChannelMarshalReadHandler(fput, fclose),
    'ChannelWeakMarshal': ChannelWeakMarshalReadHandler(localTargets),
    'BigValueMarshal': BigValueMarshalReadHandler(remoteResources),
  }

def getWriteHandlers(localTargets, localResources):
  return {
    ChannelMarshal: ChannelMarshalWriteHandler(localTargets),
    ChannelWeakMarshal: ChannelWeakMarshalWriteHandler,
    BigValueMarshal: BigValueMarshalWriteHandler(localResources),
  }
