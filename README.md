# Sanity for NuPIC

A [NuPIC](https://github.com/numenta/nupic) backend for [Sanity](https://github.com/nupic-community/sanity).

Videos:

- [See your HTM run](https://www.youtube.com/watch?v=rEQ2XVOnhDw)
  - [With Q&A](https://www.youtube.com/watch?v=OHSuydq2OW4)
- [See your HTM run: Duct tape is okay!](https://www.youtube.com/watch?v=bqu-hc4pc7Q)

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

Compile [Sanity](https://github.com/nupic-community/sanity) from ClojureScript to JavaScript. You'll need Leiningen, which you can get through `brew install leiningen`, or just follow instructions on [the website](http://leiningen.org/).

~~~
# Requires JVM
cd htmsanity/nupic/sanity
lein cljsbuild once demos
cd ..
~~~

If you can't handle the JVM, you can download Sanity precompiled here
[here](http://mrcslws.com/stuff/sanity-91337ed.zip). Copy the contents into
`htmsanity/nupic/sanity/public/demos`. Sanity will load scripts from `demos/out`.

## Run

Try an example!

~~~
# Hello world
python examples/hotgym.py

# Requires matplotlib
python examples/hotgym_plotted.py

# Requires nupic.research
python examples/research_feedback.py
~~~

Sanity will automatically open in a web browser.

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
