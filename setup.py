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

setup(name="sanity-nupic",
      version="0.0.1",
      description="NuPIC server for Sanity client",
      author="Marcus Lewis",
      author_email="mrcslws@gmail.com",
      url="https://github.com/nupic-community/sanity-nupic/",
      packages=find_packages(),
      package_data={'htmsanity': ['htmsanity/nupic/sanity/public/*',]},
      install_requires=findRequirements(),
      zip_safe=False,
     )
