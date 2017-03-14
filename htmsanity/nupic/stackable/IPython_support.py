import json
import numbers
import os
import uuid

from pkg_resources import resource_string

from IPython.display import HTML, display


def get_stackable_js():
    # path = os.path.join('package_data', 'sanity/public/stackable-bundle.js')
    # path = 'stackable-bundle.js'
    path = 'nupic/sanity/public/stackable-out/stackable-bundle.js'
    stackable_js = resource_string('htmsanity', path).decode('utf-8')
    return stackable_js


def init_notebook_mode():
    # Insert your own CSS here.
    style_inject = """
    <style>

    div.stackable-output {
      -webkit-touch-callout: none;
      -webkit-user-select: none;
      -moz-user-select: none;
      -ms-user-select: none;
      user-select: none;

      padding-bottom: 2px;
    }

    div.stackable-output svg {
      max-width: initial;
    }

      text {
      font: 10px sans-serif;
      }

      .axis path {
      fill: none;
      stroke: none;
      shape-rendering: crispEdges;
      }

      .crispLayers .layer {
      shape-rendering: crispEdges;
      }

      .axis line {
      stroke: none;
      shape-rendering: crispEdges;
      }

      .showAxis path {
      stroke: black;
      }

      .y.axis line {
      stroke: none;
      }

      .noselect {
      -webkit-touch-callout: none;
      -webkit-user-select: none;
      -moz-user-select: none;
      -ms-user-select: none;
      user-select: none;
      }

      .clickable {
      cursor: pointer;
      }

      .draggable {
      cursor: -webkit-grab;
      cursor: -moz-grab;
      cursor: grab;
      }

      .dragging .draggable,
      .dragging .clickable {
      cursor: -webkit-grabbing;
      cursor: -moz-grabbing;
      cursor: grabbing;
      }

    </style>
    """

    script_inject = u"""
    <script type='text/javascript'>
      if(!window.stackable) {{
        define('stackable', function(require, exports, module) {{
          {script}
        }});
        require(['stackable'], function(stackable) {{
          window.stackable = stackable;
        }});
      }}
    </script>
    """.format(script=get_stackable_js())

    display(HTML(style_inject + script_inject))


def insertColumnStatesAndSegmentLifetimes(csv_text):
    elementId = str(uuid.uuid1())
    addChart = """
    <div class="stackable-output" id="%s"></div>
    <script>
    require(['stackable'], function(stackable) {
      stackable.insertColumnStatesAndSegmentLifetimes(document.getElementById('%s'), '%s');
    });
    </script>
    """ % (elementId, elementId,
           csv_text.replace("\r", "\\r").replace("\n", "\\n"))

    display(HTML(addChart))
