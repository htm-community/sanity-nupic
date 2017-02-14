import platform
import sys

from setuptools import find_packages, setup

setup(name="sanity-nupic",
      version="0.0.12",
      description="NuPIC server for Sanity client",
      author="Marcus Lewis",
      author_email="mrcslws@gmail.com",
      url="https://github.com/nupic-community/sanity-nupic/",
      packages=find_packages(),
      package_data={'htmsanity': ['htmsanity/nupic/sanity/public/*',]},
      include_package_data=True,
      install_requires=[
          # Twisted 17.1.0 causes error:
          #   AttributeError: 'module' object has no attribute 'OP_NO_TLSv1_1'
          'Twisted<=16.6.0',
          'autobahn',
          'transit-python'],
      zip_safe=False,
     )
