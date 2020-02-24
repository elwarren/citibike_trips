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
cb = CitibikeTrips(username='XXX', password='XXX', save=True)
cb.get_all()
```

## Output

When executed with `save=True` the following seven files will be created in the data dir with epoch timestamps:

**Trips** contains your citibike trip data as it was presented online.

```
cb_trips_1234567890.csv
cb_trips_1234567890.json
```

Columns:

```
start_time
end_time
start_name
end_name
start_points
end_points
points
billed
duration
```

**Trips Full** contains trip data with useful lookups. Station names are decorated with geo lon+lat pairs, trip time converted from H:M pairs to total seconds, etc.

```
cb_trips_full_1234567890.csv
cb_trips_full_1234567890.json
```

Columns:

```
account_id
observed
start_time
end_time
start_name
end_name
start_points
end_points
points
billed
duration
start_id
end_id
start_terminal
end_terminal
start_lon
start_lat
end_lon
end_lat
dollars
seconds
start_epoch
end_epoch
start_iso8601
end_iso8601
start_zipcode
end_zipcode
```

**Zipcodes** contains a list of zipcode to station name pairs. Useful to track stations visited.

```
cb_zipcodes_1234567890.json
```

Columns:

```
zipcode
station_name
```

**Account** contains profile information.  Useful to track days left in membership, lifetime miles, and account balance.

```
cb_account_1234567890.json
```

**Stations** is the raw json station feed.  Useful for offline testing and historical station tracking.

```
cb_stations_1234567890.json
```

## Note

The uszipcode package is a bit heavy.  It will download and cache 9mb of zipcode data on the first run.  It requires sqlite which blocks it from being used on iOS with pythonista or in a lambda.  It might be removed in the future.

## Thanks

Special thanks to the Citibike program operated by NYC Bike Share. I
ride these bikes everyday, sometimes 3-4 trips in a single day.

Please do not abuse their servers with excessive polling. I've read the
Citibike TOS http://www.citibikenyc.com/assets/pdf/terms-of-use.pdf and
it appears to be OK to do this for personal use.

