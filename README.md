# sanity-nupic

Clone this repo, and fetch the submodules:

~~~
cd sanity-nupic
git submodule update --init --recursive
~~~

Install NuPIC. [Instructions](https://github.com/numenta/nupic)

Install `htmsanity-nupic`;

~~~
python setup.py develop --user
~~~

Now run your HTM model. Here are some examples:

~~~
# Hello world
python examples/hotgym.py

# Requires matplotlib
python examples/hotgym_plotted.py

# Requires nupic.research
python examples/research_feedback.py
~~~

To view it, you need to host `index.html` and `comportexviz`.

## Client option 1: Compile comportexviz

~~~
# Requires JVM
cd comportexviz
lein cljsbuild once demos
cd ..
~~~

Now just host the root folder `sanity-nupic` on a local webserver.

~~~
python -m SimpleHTTPServer 8000
~~~

Navigate to http://localhost:8000

## Client option 2: Download and unzip

Download [this folder](http://mrcslws.com/stuff/sanity-client.a28431d.zip), unzip it, and host it on a local webserver.

~~~
cd sanity-client.a28431d
python -m SimpleHTTPServer 8000
~~~

Navigate to http://localhost:8000
