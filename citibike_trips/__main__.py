import citibike_trips
import json
import os.path

config_file = "citibike_trips.config"
if os.path.exists(os.path.expanduser("~/.{}".format(config_file))):
    config = json.load(open(os.path.expanduser("~/.{}".format(config_file)), "r"))
elif os.path.exists(config_file):
    config = json.load(open(config_file), "r")
else:
    raise SystemExit("Need account details in {}".format(config_file))

cb = citibike_trips.CitibikeTrips(
    username=config["username"], password=config["password"], save=False
)

cb.get_trips(last_page=1)

print(json.dumps(cb.trips[0], indent=2, sort_keys=True))
