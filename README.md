# Sanity for NuPIC

A [NuPIC](https://github.com/numenta/nupic) backend for [Sanity](https://github.com/htm-community/sanity).

Videos:

- [See your HTM run](https://www.youtube.com/watch?v=rEQ2XVOnhDw)
  - [With Q&A](https://www.youtube.com/watch?v=OHSuydq2OW4)
- [See your HTM run: Duct tape is okay!](https://www.youtube.com/watch?v=bqu-hc4pc7Q)

## Install

**The easy way:**

~~~
pip install sanity-nupic --user
~~~

Current version: `0.0.8`

**The adventurous way:**

Clone `sanity-nupic`, and fetch the submodules:

~~~
cd sanity-nupic
git submodule update --init --recursive
~~~

Install the `sanity-nupic` python package;

~~~
python setup.py develop --user
~~~

Compile [Sanity](https://github.com/htm-community/sanity) from ClojureScript to JavaScript. You'll need Leiningen, which you can get through `brew install leiningen`, or just follow instructions on [the website](http://leiningen.org/).

Install Comportex, a Sanity dependency.

~~~
git clone https://github.com/htm-community/comportex.git
cd comportex
lein install
~~~

Compile Sanity to JavaScript.

~~~
# Requires JVM
cd htmsanity/nupic/sanity
lein cljsbuild once demos
~~~

## Run

**The easy way:**

Just patch your model!

~~~python
import htmsanity.nupic.runner as sanity
sanity.patchCLAModel(model)
~~~

Sanity will automatically open in a web browser.

**The other easy way:**

Try a custom example.

~~~
git clone https://github.com/htm-community/sanity-nupic.git
cd sanity-nupic

# Hello world
python examples/hotgym.py

# Requires matplotlib
python examples/hotgym_plotted.py

# Requires nupic.research
python examples/research_feedback.py
~~~

**The more adventurous way:**

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

For custom models, you'll want to create your own `SanityModel`. Read the documentation [in the code](htmsanity/nupic/model.py), and look at the [research example](examples/research_feedback.py).
