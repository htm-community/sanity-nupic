# comportexviz-nupic

This uses a [temporary fork](https://github.com/mrcslws/comportexviz/tree/nupic-hack) of ComportexViz. Specifically, the "nupic-hack" branch.

Clone this repo, and fetch the submodules:

~~~
cd comportexviz-nupic
git submodule update --init --recursive
~~~

Install dependencies:

~~~
pip install Twisted
pip install nupic
pip install autobahn
pip install transit-python
~~~

Compile ComportexViz, or download it [here](http://mrcslws.com/stuff/comportexviz.6387216.zip).

~~~
# Optional
cd comportexviz
lein cljsbuild once demos
cd ..
~~~

If you downloaded it, copy the "out" folder into `comportexviz/public/demos/`. The webpage needs to be able to find the path `comportexviz/public/demos/out/comportexviz.js`.

Host the root folder (`comportexviz-nupic`) on a local webserver.

~~~
python -m SimpleHTTPServer 8000
~~~

Run the websocket.

~~~
python examples/hotgym-plot.py
~~~

Navigate to http://localhost:8000
