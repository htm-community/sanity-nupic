from htmsanity.nupic.stackable.logging import TimeSeriesLogger


def init_notebook_mode():
    import IPython_support
    IPython_support.init_notebook_mode()


def insertColumnStatesAndSegmentLifetimes(*args, **kwargs):
    import IPython_support
    IPython_support.insertColumnStatesAndSegmentLifetimes(*args, **kwargs)
