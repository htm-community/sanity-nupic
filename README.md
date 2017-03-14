# Sanity for NuPIC

A [NuPIC](https://github.com/numenta/nupic) backend for [Sanity](https://github.com/htm-community/sanity).

Videos:

- [See your HTM run](https://www.youtube.com/watch?v=rEQ2XVOnhDw)
  - [With Q&A](https://www.youtube.com/watch?v=OHSuydq2OW4)
- [See your HTM run: Duct tape is okay!](https://www.youtube.com/watch?v=bqu-hc4pc7Q)

## How to use it

~~~
pip install sanity-nupic
~~~

Current version: `0.0.14`

Now, just patch your model.

**CLAModel**

~~~python
import htmsanity.nupic.runner as sanity
sanity.patchCLAModel(model)
~~~

**Temporal Memory**

~~~python
import htmsanity.nupic.runner as sanity
sanity.patchTM(tm)
~~~

Sanity will automatically open in a web browser.

Don't let your Python script exit. If necessary, add this to the end:

~~~python
import time
time.sleep(999999)
~~~


## How to develop it

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

## Other usage

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

# Stackable time series

See [this notebook](http://htm-community.github.io/sanity-nupic/stackable.html). You can create your own [segment lifetimes](http://mrcslws.com/blocks/2016/04/28/life-and-times-of-dendrite-segment.html) diagrams inside a notebook.
