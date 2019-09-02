# citibike_trips

Python module to get personal trip history from Citibike website.

## Install

Not released to PyPi yet.

```
$ pip install -r requirements.txt
```

## Setup

Put login credentials for citibikenyc.com in `citibike_trips.config`.

```
{"username": "xxx@xxx.com", "password": "xxx"}
```

## Usage

```
from citibike_trips import CitibikeTrips
```

## Thanks

Special thanks to the Citibike program operated by NYC Bike Share. I
ride these bikes everyday, sometimes 3-4 trips in a single day.

Please do not abuse their servers with excessive polling. I've read the
Citibike TOS http://www.citibikenyc.com/assets/pdf/terms-of-use.pdf and
it appears to be OK to do this for personal use.

