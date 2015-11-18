# comportexviz-nupic

Clone this repo, and fetch the submodules:

~~~
cd comportexviz-nupic
git submodule update --init --recursive
~~~

Install NuPIC. [Instructions](https://github.com/numenta/nupic)

Install dependencies:

~~~
pip install Twisted --user
pip install autobahn --user
pip install transit-python --user
~~~

Compile ComportexViz, or download a compiled version [here](http://mrcslws.com/stuff/comportexviz.6387216.zip).

~~~
# Optional, requires JVM
cd comportexviz
lein cljsbuild once demos
cd ..
~~~

If you downloaded it, copy the "out" folder into `comportexviz/public/demos/`. The webpage will look for the path `comportexviz/public/demos/out/comportexviz.js` on the server below.

Host the root folder (`comportexviz-nupic`) on a local webserver:

~~~
python -m SimpleHTTPServer 8000
~~~

In another terminal window, choose and run a demo:

~~~
python examples/hotgym.py

# I recommend this one, but I don't want to help you install matplotlib.
# python examples/hotgym_plotted.py
~~~

Navigate to http://localhost:8000
