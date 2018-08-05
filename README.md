# SpaceKnow assignment

This script uses SpaceKnow API to collect imagery of an area in selected time interval, segment and count features of 
a given class, and visualize the result in raster graphics format. 

## Prerequisites

Tested on Python 3.6.5. The following PyPI packages are required in order to run the script:

* Pillow - image processing library
* Requests - very convenient HTTP library
* Nose - optional, for running unit tests in PyCharm

You can either install them into your environment manually, or via 
```
pip3 install -r requirements.txt
```
If you prefer using conda,
```
conda install --yes --file requirements.txt
```
should work. Let me know if you encounter any problems.

## Running the script

To run the script on the default area with the default parameters, simply type
```
python3.6 sk_ass.py
```

To display all supported optional parameters as well as their default values, run
```
python3.6 sk_ass.py -h
```

At the moment, the following optional arguments are supported:

* `-f`: path to a geojson file specifying the input extent
* `-m`: map type, currently only `cars`
* `-d`: age of the oldest scene analyzed, in days
* `-s`: maximum allowable ground sample distance (GSD)
* `-g`: debug mode - prints more detailed runtime information (request / response messages)
* `-h`: displays help

The resulting images can be found in `./img/`, and the number of detected instances over the period is printed out in 
the console.

Only eligible scenes, i.e. with cloud coverage under 0.05 and GSD under 0.55 are analyzed.

Be patient! Based on the age of oldest scene analyzed, selected area, extent size and other factors, execution may 
take 5-20 minutes.

## Running unit tests

Running unit tests is easy, simply type
```
python3.6 test.py 
```

## Authors

* **Miroslav Kovar** [GitHub](https://github.com/mirgee), [email](miroslavkovar@protonmail.com)
