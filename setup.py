from pysspm_rhythia.__version__ import __version__
print(__version__)
from setuptools import setup, find_packages

setup(
    name="pysspm-rhythia",
    version=__version__,
    author="David Jedlovsky",
    author_email="Dev.DavidJed@gmail.com",
    description="A Python library dedicated to reading, writing, and modifying the Rhythia SSPM (.sspm) file format",
    long_description=open("README.md", encoding="UTF-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/David-Jed/pysspm",
    packages=find_packages(),
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "numpy",
    ],
    extras_require={
        "dev": [
            "pytest",
        ],
    },
    keywords=["Rhythia", "Sound space", "SSPM", "Rhythm game", "pysspm-rhythia", "pysspm", "nova", "phoenyx", "SS+M", 'sspm'],
    include_package_data=True,
)
