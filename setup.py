import platform
import sys

from setuptools import find_packages, setup

setup(name="sanity-nupic",
      version="0.0.10",
      description="NuPIC server for Sanity client",
      author="Marcus Lewis",
      author_email="mrcslws@gmail.com",
      url="https://github.com/nupic-community/sanity-nupic/",
      packages=find_packages(),
      package_data={'htmsanity': ['htmsanity/nupic/sanity/public/*',]},
      include_package_data=True,
      install_requires=['Twisted', 'autobahn', 'transit-python'],
      zip_safe=False,
     )
