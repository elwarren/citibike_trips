# citibike_trips

Python module to get personal trip history from Citibike website.

## Install

Not released to PyPi yet.

```
$ pip install -r requirements.txt
```

## Usage

```
from citibike_trips import CitibikeTrips
cb = CitibikeTrips(username='XXX', password='XXX', save=True)
cb.get_trips_all()
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
```

**Account** contains profile information.  Useful to track days left in membership, lifetime miles, and account balance.

```
cb_account_1234567890.json
```

**Stations** is the raw json station feed.  Useful for offline testing and historical station tracking.

```
cb_stations_1234567890.json
```

## Example

The provided `citibike-trips` outputs your trips to JSON. It has switches to enable debug output for authentication and html parsing if needed.

```
usage: citibike-trips [-h] [-u USERNAME] [-p PASSWORD] [-c CONFIG] [-v] [-d] [-r RECENT] [-a] [-b] [-x] [-k KEEP] [-o OUTPUT]

Citibike personal trip history download.

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        Citibike account username
  -p PASSWORD, --password PASSWORD
                        Citibike account password
  -c CONFIG, --config CONFIG
                        Config file
  -v, --verbose         Enable verbose output
  -d, --debug           Enable debug output
  -r RECENT, --recent RECENT
                        Number of recent trip pages down get. Defaults to 1, use 0 for all.
  -a, --account         Show account data instead of trips.
  -b, --bikeangels      Collect Bike Angels stats from profile
  -x, --extended        Enable extended reporting format
  -k KEEP, --keep KEEP  Keep retrieved files in this cache dir
  -o OUTPUT, --output OUTPUT
                        Output in json or csv

```

### Setup

Put login credentials in `~/.citibike_trips.config`.

```
{"username": "xxx@xxx.com", "password": "xxx"}
```

## Thanks

Special thanks to the Citibike program operated by NYC Bike Share. I
ride these bikes everyday, sometimes 3-4 trips in a single day.

Please do not abuse their servers with excessive polling. I've read the
Citibike TOS http://www.citibikenyc.com/assets/pdf/terms-of-use.pdf and
it appears to be OK to do this for personal use.

## License

>You can check out the full license [here](https://github.com/elwarren/citibike_trips/blob/master/LICENSE)

This project is licensed under the terms of the **MIT** license.