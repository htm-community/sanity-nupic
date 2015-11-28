# Sanity for NuPIC

A [NuPIC](https://github.com/numenta/nupic) backend for [Sanity](https://github.com/nupic-community/sanity).

## Install

Install NuPIC. [Instructions](https://github.com/numenta/nupic)

Clone `sanity-nupic`, and fetch the submodules:

~~~
cd sanity-nupic
git submodule update --init --recursive
~~~

Install the `sanity-nupic` python package;

~~~
python setup.py develop --user
~~~

Compile [Sanity](https://github.com/nupic-community/sanity) from ClojureScript to JavaScript.

~~~
# Requires JVM
cd sanity
lein cljsbuild once demos
cd ..
~~~

If you can't handle the JVM or [Leiningen](http://leiningen.org/), you can download and host [this folder](http://mrcslws.com/stuff/sanity-client.0c42b25.zip).

## Run

There are two parts to this:

1. Host Sanity client on a webserver.
2. Run a NuPIC experiment.

For part 1, you can just host the `sanity-nupic` folder. Make sure you've compiled Sanity.

~~~
python -m SimpleHTTPServer 8000
~~~

For part 2, here are some examples:

~~~
# Hello world
python examples/hotgym.py

# Requires matplotlib
python examples/hotgym_plotted.py

# Requires nupic.research
python examples/research_feedback.py
~~~

Now navigate to `http://localhost:8000`

## Use

Here's an example that visualizes a CLAModel.

~~~python
from nupic.frameworks.opf.modelfactory import ModelFactory

from htmsanity.nupic.runner import SanityRunner
from htmsanity.nupic.model import CLASanityModel

# You create something like this.
class HelloModel(CLASanityModel):
    def __init__(self):
        MODEL_PARAMS = {
            # Your choice
        }
        self.model = ModelFactory.create(MODEL_PARAMS)
        self.lastInput = -1
        super(HelloModel, self).__init__(self.model)

    def step(self):
        self.lastInput = (self.lastInput + 1) % 12
        self.model.run({
            'myInput': self.lastInput,
        })

    def getInputDisplayText(self):
        return {
            'myInput': self.lastInput,
        }

sanityModel = HelloModel()
runner = SanityRunner(sanityModel)
runner.start()
~~~

For a real-world CLAModel example, see [hotgym](examples/hotgym.py) or [hotgym plotted](examples/hotgym_plotted.py).

For custom models, you'll want to create your own `SanityModel`. Read the documentation [in the code](htmsanity/nupic/model.py), and look at the [research](examples/research_feedback.py) [examples](examples/research_union_pooler.py).
