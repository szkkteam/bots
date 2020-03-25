from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='bots',
    version='0.0.11',
    description='Automated Bots',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/szkkteam/bots.git',
    author='Istvan Rusics',
    author_email='szkkteam1@gmail.com',
    license='MIT license',
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    zip_safe=False
)
