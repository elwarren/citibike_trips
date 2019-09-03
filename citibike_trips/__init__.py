import json
import logging
import requests
from bs4 import BeautifulSoup
import time
import datetime
import pytz


log = logging.getLogger(__name__)
__version__ = '0.0.1'
DTS = '%m/%d/%Y %H:%M:%S %p'
TZS = 'US/Eastern'
TZ=pytz.timezone(TZS)


class CitibikeTrips:
    username: str
    password: str
    t: int
    w: int
    account: object
    stations: object
    trips: object
    save: bool
    data_dir: str
    url_stations: str
    url_member_base: str
    url_login_get: str
    url_login_post: str
    url_profile: str
    url_last: str

    def __init__(self,
                 username,
                 password,
                 offline=False,
                 save=False,
                 data_dir='./data',
                 http_timeout=60,
                 http_wait=1,
                 url_stations='https://layer.bicyclesharing.net/map/v1/nyc/stations',
                 url_member_base='https://member.citibikenyc.com',
                 user_agent='curl',
                 ):
        """

        :type username: str
        :type password: str
        :type offline: bool
        :type save: bool
        :type data_dir: str
        :type http_timeout: int
        :type http_wait: int
        :type url_stations: str
        :type url_member_base: str
        :type user_agent: str
        """

        log.debug('init')
        self.ts = int(time.time())
        self.username = username
        self.password = password
        self.offline = offline
        self.save = save
        self.data_dir = data_dir
        self.t = http_timeout
        self.w = http_wait
        self.s = requests.session()
        self.url_stations = url_stations
        self.url_member_base = url_member_base
        self.url_login_get = '{}/profile/login'.format(self.url_member_base)
        self.url_login_post = '{}/profile/login_check'.format(self.url_member_base)
        self.url_profile = '{}/profile/'.format(self.url_member_base)
        self.url_last = None
        self.trips = []
        self.stations = {}

        self.account = {
            'trips': {
                'lifetime': None,
            },
            'points': {
                'month': None,
                'annual': None,
                'lifetime': None,
            },
            'last_trip': {
                'date': [],
                'station': [],
            },
            'bike_key': {
                'number': None,
                'status': None,
            },
            'membership_status': {
                'type': None,
                'status': None,
                'expiration': None,
            },
            'billing_summary': {
                'next_billing_date': None,
                'current_balance': None,
            },
            'billing_information': {
                'zip_postal_code': None,
                'credit_card': None,
            },
            'profile': {
                'first_name': None,
                'last name': None,
                'user_name': None,
                'date_of_birth': None,
                'gender': None,
                'phone': None,
                'email': None,
                'member_since': None,
                'bike_angel_since': None,
            },
            'my_statistics': {
                'number_of_trips': None,
                'total_usage_time': None,
                'distance_traveled': None,
                'gas_saved': None,
                'co2_reduced': None,
                'bike_angels_current': None,
                'bike_angels_annual': None,
                'bike_angels_lifetime': None,
            },
            'id': [],
            'ts': self.ts,
        }

    def get_trips(self, last_page=0, file=None):
        if file:
            log.debug('loading trips from {}'.format(file))
            with open(file, 'r', encoding='utf-8') as f:
                self.trips = json.load(f)
            return(self.trips)

        if not self.login():
            return(False)

        self.extract_profile()
        self.get_trips_loop(last_page=last_page)
        self.get_stations()

        if self.save:
            log.info('saving output')
            self.write_trips_csv('{}/cb_trips_{}.csv'.format(self.data_dir, self.ts))
            self.write_trips_json('{}/cb_trips_{}.json'.format(self.data_dir, self.ts))
            self.write_account_json('{}/cb_account_{}.json'.format(self.data_dir, self.ts))
            self.write_stations_json('{}/cb_stations_{}.json'.format(self.data_dir, self.ts))
            self.write_trips_full_csv('{}/cb_trips_full_{}.csv'.format(self.data_dir, self.ts))

        log.info('done')

    def get_last_trip(self):
        if not self.login():
            return(False)
        self.extract_profile()
        self.get_trips_loop(last_page=1)
        log.info('done')

    def login(self):
        log.info('login')
        # Find csrf token for login
        res = self.s.get(self.url_login_get, timeout=self.t)
        soup = BeautifulSoup(res.text, "html5lib")
        self.csrf = soup.find("input", {'name': '_login_csrf_security_token'}).get('value')

        log.debug('csrf: {}'.format(self.csrf))

        payload = {
            '_username': self.username,
            '_password': self.password,
            '_login_csrf_security_token': self.csrf,
        }

        # post login
        res = self.s.post(
            self.url_login_post,
            data=payload,
            headers=dict(referer=self.url_login_get)
        )

        log.debug('POST login {}'.format(res.status_code))
        if res.status_code == requests.codes.ok:
            log.debug('POST login pass')
            return(True)
        else:
            log.warning('POST login fail')
            return(False)

    def get_account_soup(self):
        # get profile page
        res = self.s.get(self.url_profile, headers=dict(referer=self.url_profile))
        self.soup_profile = BeautifulSoup(res.content, "html5lib")
        return(self.soup_profile)

    def extract_profile(self):
        if not hasattr('self', 'soup_profile'):
            self.get_account_soup()
        soup = self.soup_profile

        # extract stats
        _ = int(soup.find('div', {
            'class': 'ed-panel__info__value ed-panel__info__value_member-stats-for-period ed-panel__info__value_member-stats-for-period_lifetime'}).text)
        self.account['trips']['lifetime'] = _

        # 'August 11th, 2019 12:47 PM'
        _ = soup.find('div', {'class': 'ed-panel__info__value__part ed-panel__info__value__part_start-date'}).text
        self.account['last_trip']['date'].append(_)

        _ = soup.find('div', {'class': 'ed-panel__info__value__part ed-panel__info__value__part_end-date'}).text
        self.account['last_trip']['date'].append(_)

        # '10 Ave & W 28 St'
        _ = soup.find('div',
                      {'class': 'ed-panel__info__value__part ed-panel__info__value__part_start-station-name'}).text
        self.account['last_trip']['station'].append(_)

        _ = soup.find('div', {'class': 'ed-panel__info__value__part ed-panel__info__value__part_end-station-name'}).text
        self.account['last_trip']['station'].append(_)

        # extract digits from string '70 points (August)'
        _ = int(soup.find('div', {'class': 'ed-panel__info__value__part'}).text.split(' ')[0])
        self.account['points']['month'] = _
        self.account['my_statistics']['bike_angels_current'] = _

        _ = int(
            soup.find('div', {'class': 'ed-panel__info__value__part ed-panel__info__value__part_1'}).text.split(' ')[0])
        self.account['points']['annual'] = _
        self.account['my_statistics']['bike_angels_annual'] = _

        _ = int(
            soup.find('div', {'class': 'ed-panel__info__value__part ed-panel__info__value__part_2'}).text.split(' ')[0])
        self.account['points']['lifetime'] = _
        self.account['my_statistics']['bike_angels_lifetime'] = _

        log.debug(self.account)
        return(self.account)

    def gen_trips_url_num(self, page_num):
        """generate url for individual trip page"""
        _ = '{}?pageNumber={}'.format(self.trips_url, page_num)
        log.debug('Trips page url {}'.format(_))
        return(_)

    def get_trips_links(self):
        """Extract trips link from profile and number of last trips page"""

        if not self.soup_profile:
            self.get_account_soup()
        soup = self.soup_profile

        self.trips_link = soup.find('li', {
            'class': 'ed-profile-menu__link ed-profile-menu__link_trips ed-profile-menu__link_level1'}).a.get('href')
        log.info('Trips link {}'.format(self.trips_link))
        self.trips_url = '{}{}'.format(self.url_member_base, self.trips_link)
        log.info('Trips base {}'.format(self.trips_url))

        # extract unique account id from trip link, this is different than bike key
        # TODO test account with multiple riders?
        self.account['id'].append(self.trips_link.split('/')[-1])

        soup = self.get_trips_soup()

        self.trips_last = int(soup.find('a', {
            'class': 'ed-paginated-navigation__pages-group__link_last ed-paginated-navigation__pages-group__link'}).get(
            'href').split('=')[1])
        log.info(self.trips_last)

    def get_trips_soup(self, page_num=1):
        page_url = self.gen_trips_url_num(page_num)
        log.info('get_trips_page {}'.format(page_url))
        res = self.s.get(
            page_url,
            headers=dict(referer=self.url_profile)
        )

        if res.status_code == requests.codes.ok:
            log.info('GET trips page {} PASS'.format(page_num))
            self.url_last = page_url
        else:
            log.info('GET trips page {} FAIL'.format(page_num))
            return(False)

        soup = BeautifulSoup(res.content, "html5lib")
        return(soup)

    def get_trips_loop(self, last_page=0):
        if not hasattr('self', 'trips_last'):
            self.get_trips_links()

        if 0 == last_page:
            last_page = self.trips_last

        log.info('Grabbing trips from 1 to {}'.format(last_page))
        for tp in range(1, last_page + 1):
            log.info('get trip {}'.format(tp))
            soup = self.get_trips_soup(tp)
            trips = self.extract_trip_data(soup)
            self.trips.extend(trips)

        log.info('total trips {}'.format(len(self.trips)))

    def extract_trip_data(self, soup):

        table = soup.find("table", {"class": "ed-html-table ed-html-table_trip"})
        log.debug('Found trip table: {}'.format(table))

        trips = []
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            log.debug('trip table row cells {}'.format(len(cells)))
            # first tr row is th header instead of td data cells
            if len(cells) < 1:
                # skip th header row or other possibly empty row
                continue

            _ = cells[0].find_all('div')
            start_station = _[0].text.strip()
            start_time = _[1].text.strip()
            try:
                start_points = _[2].text.strip()
            except:
                start_points = '0'

            _ = cells[1].find_all('div')
            end_station = _[0].text.strip()
            end_time = _[1].text.strip()
            try:
                end_points = _[2].text.strip()
            except:
                end_points = '0'

            billed = cells[2].get_text().strip()
            duration = cells[3].get_text().strip()
            points = cells[4].get_text().strip().split(' ')[0]

            trip = (start_station, end_station, start_time, end_time, start_points, end_points, billed, duration, points)
            trips.append(trip)

        return(trips)

    def write_stations_json(self, file):
        log.info('writing stations json to {}'.format(file))
        with open(file, 'w') as f:
            f.write(json.dumps(self.stations, indent=2 ))

    def write_account_json(self, file):
        log.info('writing account json to {}'.format(file))
        with open(file, 'w') as f:
            f.write(json.dumps(self.account, indent=2 ))

    def write_trips_json(self, file):
        log.info('writing trips json to {}'.format(file))
        with open(file, 'w') as f:
            f.write(json.dumps(self.trips, indent=2 ))

    def write_trips_csv(self, file):
        import csv
        log.info('writing trips csv to {}'.format(file))
        with open(file, 'w') as f:
            fieldnames = (
                'start_time', 'end_time',
                'start_name', 'end_name',
                'start_points', 'end_points',
                'billed', 'duration', 'points',
            )
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            writer.writerows(self.trips)

    def write_trips_full_csv(self, file):
        self.hydrate_trips()
        import csv
        log.info('writing trips csv to {}'.format(file))
        with open(file, 'w') as f:
            fieldnames = (
                'account_id', 'observed',
                'start_time', 'end_time',
                'start_name', 'end_name',
                'start_points', 'end_points',
                'billed', 'duration', 'points',
                'start_id', 'end_id',
                'start_terminal', 'end_terminal',
                'start_lon', 'start_lat',
                'end_lon', 'end_lat',
                'dollars', 'seconds',
                'start_epoch', 'end_epoch',
            )
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            writer.writerows(self.trips_full)

    def load_json(self, ts):
        self.ts = ts

        file = '{}/cb_trips_{}.json'.format(self.data_dir, self.ts)
        log.debug('loading trips from {}'.format(file))
        with open(file, 'r', encoding='utf-8') as f:
            self.trips = json.load(f)

        file = '{}/cb_account_{}.json'.format(self.data_dir, self.ts)
        log.debug('loading account from {}'.format(file))
        with open(file, 'r', encoding='utf-8') as f:
            self.account = json.load(f)

        file = '{}/cb_stations_{}.json'.format(self.data_dir, self.ts)
        log.debug('loading stations from {}'.format(file))
        with open(file, 'r', encoding='utf-8') as f:
            self.stations = json.load(f)

    def get_stations(self, file=None):
        if file:
            log.debug('loading stations from {}'.format(file))
            with open(file, 'r', encoding='utf-8') as f:
                self.stations = json.load(f)['features']
        else:
            log.debug('getting stations from {}'.format(self.url_stations))
            r = self.s.get(self.url_stations, timeout=self.t)
            self.stations = r.json()['features']

    def hydrate_trips(self, datestring=True, locations=True):
        log.info('hydrating')
        self.trips_full = []
        for trip in self.trips:
            log.debug('start station {}'.format(trip[2]))

            # Starting station exceptions happen when stations don't exist anymore
            # "W 17 St & 9 Ave" is in history but cannot lookup in stations.json
            try:
                start_station = self.station_by_name(trip[2])

                start_id = start_station['properties']['station_id']
                start_terminal = start_station['properties']['terminal']
                dollars = self.dollars_to_float(trip[7])
                seconds = self.str_to_secs(trip[6])

                start_dt = datetime.datetime.strptime(trip[0], DTS)
                start_dtz = TZ.localize(start_dt)
                start_epoch = int(start_dtz.timestamp())

                start_loc = start_station['geometry']['coordinates']
                start_lon = start_station['geometry']['coordinates'][0]
                start_lat = start_station['geometry']['coordinates'][1]
            except:
                start_id = '-'
                start_terminal = '-'

                start_dt = datetime.datetime.strptime(trip[0], DTS)
                start_dtz = TZ.localize(start_dt)
                start_epoch = int(start_dtz.timestamp())

                start_loc = '-'
                start_lon = '-'
                start_lat = '-'

            # Ending station exceptions happen when trips are not closed properly
            # bikes not returned, dock malfunctions, whatever
            try:
                end_station = self.station_by_name(trip[3])
                end_id = end_station['properties']['station_id']
                end_terminal = end_station['properties']['terminal']
                end_loc = end_station['geometry']['coordinates']
                end_lon = end_station['geometry']['coordinates'][0]
                end_lat = end_station['geometry']['coordinates'][1]
                end_dt = datetime.datetime.strptime(trip[0], DTS)
                end_dtz = TZ.localize(end_dt)
                end_epoch = int(end_dtz.timestamp())
                dollars = self.dollars_to_float(trip[7])
                seconds = self.str_to_secs(trip[6])
            except:
                end_station = '-'
                end_id = '-'
                end_terminal = '-'
                end_loc = '-'
                end_lon = '-'
                end_lat = '-'
                end_dt = '-'
                end_dtz = '-'
                dollars = 0.0
                seconds = 0

            row = []
            row.append(self.account['id'][0])
            row.append(self.ts)
            row.extend(trip)
            row.extend([
                start_id, end_id,
                start_terminal, end_terminal,
                start_lon, start_lat,
                end_lon, end_lat,
                dollars, seconds,
                start_epoch, end_epoch,
            ])
            self.trips_full.append(row)

    def str_to_secs(self, st):
        '''convert string of minutes and seconds to seconds'''
        m, sm, s, ss = st.split(' ')
        secs = int(s) + int(m) * 60
        return (secs)

    def dollars_to_float(self, st):
        '''convert us currency string to float'''
        dollars = float(st[2:])
        return (dollars)

    def loc_by_name(self, name):
        try:
            station = [_ for _ in self.stations if name == _['properties']['name']]
            log.debug('searching for station {} found {}'.format(name, station))
            return(station[0])
        except:
            log.debug('searching for station {} found None')
            return(None)

    def station_by_name(self, name):
        try:
            station = [_ for _ in self.stations if name == _['properties']['name']]
            log.debug('searching for station {} found {}'.format(name, station))
            return(station[0])
        except:
            log.debug('searching for station {} found None'.format(name))
            return(None)

    def station_by_location(self, location):
        try:
            station = [_ for _ in self.stations if location == _['geometry']['coordinates']]
            log.debug('searching for location {} found {}'.format(location, station))
            return(station[0])
        except:
            log.debug('searching for location {} found None')
            return(None)

    def station_by_id(self, id):
        try:
            station = [_ for _ in self.stations if _['properties']['station_id'] == id]
            log.debug('searching for station_id {} found {}'.format(id, station))
            return(station[0])
        except:
            log.debug('searching for station_id {} found None'.format(id))
            return(None)

    def all_routes(self):
        routes = [ (x[2], x[3]) for x in self.trips ]
        return(routes)

