from setuptools import setup, find_packages

with open("../README.md","r") as fh:
    long_description = fh.read()

setup(
    name="noexiit",
    version="0.0.0",
    author="Han Kim",
    author_email="hankim@caltech.edu",
    description="Commands for controlling NOEXIIT hardware.",
    long_description=long_description,
    url="https://github.com/hanhanhan-kim/noexiit",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3"
    ],
    entry_points={
        "console_scripts": ["noexiit=noexiit.noexiit:cli"]
    },
    install_requires=[
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "requests",
        "pyserial",
        "pyyaml",
        "tqdm",
        "click"
    ]

)