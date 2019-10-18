import re
import codecs
from setuptools import setup

with codecs.open('README.txt', encoding='utf-8') as f:
    long_description = f.read()

with codecs.open("easy_py_server/__init__.py", encoding="utf8") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)

setup(name='easy_py_server',
      version=version,
      description='A flexible plugin providing reliable HTTP service for your projects',
      author='Zhengyue Huang',
      author_email='huangzhengyue.1996@gmail.com',
      url='https://github.com/scientificRat/easy_py_server.git',
      packages=['easy_py_server'],
      install_requires=['Pillow', 'termcolor'],
      long_description=long_description,
      classifiers=[
          "Programming Language :: Python :: 3",
          "Development Status :: 4 - Beta",
          "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
      ],
      python_requires='>=3.5',
      )
