import io
import re
import codecs
from setuptools import setup

with codecs.open('README.md', encoding='utf-8') as f:
    long_description = f.read()

with io.open("easy_py_server/__init__.py", "rt", encoding="utf8") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)

setup(name='easy_py_server',
      version=version,
      description='A simple and easy python web framework',
      author='scientificRat',
      author_email='huangzhengyue.1996@gmail.com',
      url='',
      packages=['easy_py_server'],
      install_requires=['Pillow', 'termcolor'],
      long_description=long_description,
      )
