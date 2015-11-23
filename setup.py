import platform
import sys

from setuptools import find_packages, setup


def findRequirements():
  """
  Read the requirements.txt file and parse into requirements for setup's
  install_requirements option.
  """
  return [
    line.strip()
    for line in open("requirements.txt").readlines()
    if not line.startswith("#")
  ]

setup(name="htmsanity-nupic",
      version="0.0.1",
      description="NuPIC server for Sanity client",
      author="Marcus Lewis",
      author_email="mrcslws@gmail.com",
      url="https://github.com/mrcslws/comportexviz-nupic",
      packages=find_packages(),
      install_requires=findRequirements(),
     )
