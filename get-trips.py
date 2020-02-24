#!/usr/bin/env python3
import argparse
from citibike_trips import CitibikeTrips

parser = argparse.ArgumentParser(description="Citibike personal trip history download.")
parser.add_argument("-u", "--username", required=True, type=str)
parser.add_argument("-p", "--password", required=True, type=str)
args = parser.parse_args()
cb = CitibikeTrips(username=args.username, password=args.password, save=True)
cb.get_all()
