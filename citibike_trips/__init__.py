import json
import logging
import browser_cookie3
import requests
from bs4 import BeautifulSoup
import time
import datetime
import pytz


log = logging.getLogger(__name__)

__version__ = "0.0.3"
DTS = "%m/%d/%Y %H:%M:%S %p"
TZS = "US/Eastern"
TZ = pytz.timezone(TZS)


class CitibikeTrips:
    username: str
    password: str
    t: int
    w: int
    account: object
    stations: object
    trips: object
    recent: int
    output: str
    keep: str
    jar: str
    data_dir: str
    verbose: bool
    debug: bool
    url_stations: str
    url_member_base: str
    url_login_get: str
    url_login_post: str
    url_profile: str
    url_last: str

    def __init__(
        self,
        username,
        password,
        ba=False,
        jar=None,
        output=False,
        recent=1,
        keep=False,
        verbose=False,
        debug=False,
        extended=False,
        http_timeout=60,
        http_wait=1,
        url_stations="https://layer.bicyclesharing.net/map/v1/nyc/stations",
        url_member_base="https://member.citibikenyc.com",
        user_agent="curl",
    ):
        """

        :type username: str
        :type password: str
        :type ba: bool
        :type jar: str
        :type output: str
        :type recent: int
        :type keep: str
        :type verbose: bool
        :type debug: bool
        :type extended: bool
        :type http_timeout: int
        :type http_wait: int
        :type url_stations: str
        :type url_member_base: str
        :type user_agent: str
        """

        log.debug("init")
        self.ts = int(time.time())
        self.username = username
        self.password = password
        self.ba = ba
        self.output = output
        self.recent = recent
        self.keep = keep
        self.data_dir = keep
        self.verbose = verbose
        self.debug = debug
        self.extended = extended
        self.url_stations = url_stations
        self.url_member_base = url_member_base
        self.url_login_get = "{}/profile/login".format(self.url_member_base)
        self.url_login_post = "{}/profile/login_check".format(self.url_member_base)
        self.url_profile = "{}/profile/".format(self.url_member_base)
        self.url_last = None
        self.t = http_timeout
        self.w = http_wait
        self.s = requests.session()
        if jar:
            self.jar = jar
            self.cj = browser_cookie3.firefox(domain_name=self.url_member_base, cookie_file=self.jar)
            self.s.cookies = self.cj
        self.trips = []
        self.trips_full = None
        self.stations = {}

        self.account = {
            "trips": {"lifetime": None,},
            "last_trip": {"date": [], "station": [], "trip_time": None, "bike_angels_points": None,},
            "bike_key": {"number": None, "status": None,},
            "membership_status": {
                "current": {"type": None, "status": None, "expiration": None,},
                "next": {"type": None, "status": None, "start": None, "expiration": None,},
            },
            "billing_summary": {"next_billing_date": None, "current_balance": None,},
            "billing_information": {"postal_code": None,},
            "profile": {
                "first_name": None,
                "last_name": None,
                "user_name": None,
                "date_of_birth": None,
                "gender": None,
                "phone": None,
                "email": None,
                "member_since": None,
                "bike_angel_since": None,
            },
            "my_statistics": {
                "number_of_trips": None,
                "total_usage_time": None,
                "distance_traveled": None,
                "gas_saved": None,
                "co2_reduced": None,
                "bike_angels_current": None,
                "bike_angels_annual": None,
                "bike_angels_lifetime": None,
            },
            "id": [],
            "ts": self.ts,
        }

        self.csv_header = (
            "start_time",
            "end_time",
            "start_name",
            "end_name",
            "start_points",
            "end_points",
            "points",
            "billed",
            "duration",
        )

        self.csv_header_full = (
            "account_id",
            "observed",
            "start_time",
            "end_time",
            "start_name",
            "end_name",
            "start_points",
            "end_points",
            "points",
            "billed",
            "duration",
            "start_id",
            "end_id",
            "start_terminal",
            "end_terminal",
            "start_lon",
            "start_lat",
            "end_lon",
            "end_lat",
            "dollars",
            "seconds",
            "start_epoch",
            "end_epoch",
            "start_iso8601",
            "end_iso8601",
        )

    def load_trips(self, file=None):
        """Load trips object from json file"""

        log.info("loading trips from {}".format(file))
        with open(file, "r", encoding="utf-8") as f:
            self.trips = json.load(f)

    def load_trips_full(self, file=None):
        """Load extended trips object from json file"""

        log.info("loading extended trips from {}".format(file))
        with open(file, "r", encoding="utf-8") as f:
            self.trips_full = json.load(f)

    def get_trips(self, last_page=0):
        """Get all trips and write data to disk. Calls login if needed."""
        if not self.login():
            return False

        self.extract_profile()
        self.get_trips_loop(last_page=last_page)
        self.get_stations()

        if self.extended:
            self.hydrate_trips()

        if self.keep:
            self.save_account()
            self.save_stations()
            self.save_trips()

        if self.extended:
            return self.trips_full
        else:
            return self.trips

    def get_account(self):
        """Get account data. Calls login if needed."""
        if not self.login():
            return False

        self.extract_profile()

        if self.keep:
            self.save_account()

        return self.account

    def save_account(self):
        log.info("saving account output")
        self.write_account_json("{}/cb_account_{}.json".format(self.data_dir, self.ts))

    def save_stations(self):
        log.info("saving stations output")
        self.write_stations_json("{}/cb_stations_{}.json".format(self.data_dir, self.ts))

    def save_trips(self):
        log.info("saving trips output")
        self.write_trips_csv("{}/cb_trips_{}.csv".format(self.data_dir, self.ts))
        self.write_trips_json("{}/cb_trips_{}.json".format(self.data_dir, self.ts))

        if self.extended:
            # hydrate is automatically called by write_trips_full
            self.write_trips_full_csv("{}/cb_trips_full_{}.csv".format(self.data_dir, self.ts))
            self.write_trips_full_json("{}/cb_trips_full_{}.json".format(self.data_dir, self.ts))

    def get_trips_recent(self):
        """Get only the most recent trips page. Calls login if needed."""
        return self.get_trips(self, last_page=1)

    def login(self):
        """Login to citibike website and return True or False."""

        log.info("login")
        # Find csrf token for login
        res = self.s.get(self.url_login_get, timeout=self.t)
        soup = BeautifulSoup(res.text, "html5lib")
        self.csrf = soup.find("input", {"name": "_login_csrf_security_token"}).get("value")

        log.debug("Found csrf: {}".format(self.csrf))

        if hasattr(self, "cj"):
            return True
        else:
            payload = {
                "_username": self.username,
                "_password": self.password,
                "_login_csrf_security_token": self.csrf,
            }

            # post login
            res = self.s.post(
                self.url_login_post, data=payload, allow_redirects=False, headers=dict(referer=self.url_login_get)
            )

            log.debug("POST login status {}".format(res.status_code))
            if res.status_code == requests.codes["ok"]:
                log.debug("POST login pass")
                # TODO as of 20200712 incorrect password returns 200 and results in soup throwing AttributeError: 'NoneType' object has no attribute 'text'
                # TODO as of 20200726 recaptcha added and throws 303 instead
                return True
            elif res.status_code == 303:
                log.warn("POST login fail 303 probably reCAPTCHA")
                return False
            else:
                log.warning("POST login fail")
                return False

    def get_account_soup(self):
        """ get profile page and return soup object."""

        res = self.s.get(self.url_profile, headers=dict(referer=self.url_profile))
        self.soup_profile = BeautifulSoup(res.content, "html5lib")
        return self.soup_profile

    def extract_profile(self):
        """Use beautiful soup to search and extract profile data from account page. Will request account page if soup_profile does not exist."""

        log.info("Extract profile from account page")

        if not hasattr("self", "soup_profile"):
            self.get_account_soup()
        soup = self.soup_profile

        self.account["profile"]["first_name"] = self.from_soup_get_profile_first_name(soup)
        self.account["profile"]["last_name"] = self.from_soup_get_profile_last_name(soup)
        self.account["profile"]["user_name"] = self.from_soup_get_profile_user_name(soup)
        self.account["profile"]["date_of_birth"] = self.from_soup_get_profile_date_of_birth(soup)
        self.account["profile"]["gender"] = self.from_soup_get_profile_gender(soup)
        self.account["profile"]["phone"] = self.from_soup_get_profile_phone_number(soup)
        self.account["profile"]["email"] = self.from_soup_get_profile_email(soup)
        self.account["profile"]["member_since"] = self.from_soup_get_profile_member_since(soup)
        self.account["profile"]["bike_angel_since"] = self.from_soup_get_profile_bike_angel_since(soup)

        self.account["trips"]["lifetime"] = self.from_soup_get_lifetime_stats(soup)

        self.account["my_statistics"]["number_of_trips"] = self.from_soup_get_lifetime_stats_number_of_trips(soup)
        self.account["my_statistics"]["total_usage_time"] = self.from_soup_get_lifetime_stats_total_usage_time(soup)
        self.account["my_statistics"]["distance_traveled"] = self.from_soup_get_lifetime_stats_distance_traveled(soup)
        self.account["my_statistics"]["gas_saved"] = self.from_soup_get_lifetime_stats_gas_saved(soup)
        self.account["my_statistics"]["co2_reduced"] = self.from_soup_get_lifetime_stats_co2_reduced(soup)

        self.account["last_trip"]["date"] = self.from_soup_get_last_trip_dates(soup)
        self.account["last_trip"]["station"] = self.from_soup_get_last_trip_stations(soup)
        self.account["last_trip"]["trip_time"] = self.from_soup_get_last_trip_time(soup)

        self.account["bike_key"]["number"] = self.from_soup_get_bike_key_number(soup)
        self.account["bike_key"]["status"] = self.from_soup_get_bike_key_status(soup)

        self.account["membership_status"]["current"]["type"] = self.from_soup_get_membership_current_type(soup)
        self.account["membership_status"]["current"]["status"] = self.from_soup_get_membership_current_status(soup)
        self.account["membership_status"]["current"]["expiration"] = self.from_soup_get_membership_current_expiration(
            soup
        )

        self.account["membership_status"]["next"]["type"] = self.from_soup_get_membership_next_type(soup)
        self.account["membership_status"]["next"]["status"] = self.from_soup_get_membership_next_status(soup)
        self.account["membership_status"]["next"]["start"] = self.from_soup_get_membership_next_start(soup)
        self.account["membership_status"]["next"]["expiration"] = self.from_soup_get_membership_next_expiration(soup)

        self.account["billing_summary"]["next_billing_date"] = self.from_soup_get_billing_summary_next_billing_date(
            soup
        )
        self.account["billing_summary"]["current_balance"] = self.from_soup_get_billing_summary_current_balance(soup)

        self.account["billing_information"]["postal_code"] = self.from_soup_get_billing_info_postal_code(soup)

        if self.ba:
            # these should work because try/except but we'll be safe
            log.info("Extracting bikeangels from profile")
            self.account["my_statistics"]["bike_angels_current"] = self.from_soup_get_ba_points_current(soup)
            self.account["my_statistics"]["bike_angels_annual"] = self.from_soup_get_ba_points_annual(soup)
            self.account["my_statistics"]["bike_angels_lifetime"] = self.from_soup_get_ba_points_lifetime(soup)

            self.account["last_trip"]["bike_angels_points"] = self.from_soup_get_last_trip_bike_angels_points(soup)

        log.debug(self.account)
        return self.account

    def from_soup_get_lifetime_stats(self, soup):
        """Extract lifetime stats from profile soup"""

        try:
            # extract stats
            _ = int(
                soup.find(
                    "div",
                    {
                        "class": "ed-panel__info__value ed-panel__info__value_member-stats-for-period ed-panel__info__value_member-stats-for-period_lifetime"
                    },
                ).text
            )
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_lifetime_stats_number_of_trips(self, soup):
        """Extract lifetime stats for number of trips from profile soup

            <div class="ed-panel__info ed-panel__info_member-stats-for-period ed-panel__info_member-stats-for-period_lifetime ed-panel__info ed-panel__info_with-label">
            <div class="ed-panel__info__label ed-panel__info__label_member-stats-for-period ed-panel__info__label_member-stats-for-period_lifetime">Number of trips</div>
            <div class="ed-panel__info__value ed-panel__info__value_member-stats-for-period ed-panel__info__value_member-stats-for-period_lifetime">1040</div>"""

        try:
            _ = soup.find(
                "div",
                {
                    "class": "ed-panel__info__value ed-panel__info__value_member-stats-for-period ed-panel__info__value_member-stats-for-period_lifetime"
                },
            ).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_lifetime_stats_total_usage_time(self, soup):
        """Extract lifetime stats for usage time from profile soup

            <div class="ed-panel__info ed-panel__info_member-stats-for-period ed-panel__info ed-panel__info_with-label">
            <div class="ed-panel__info__label ed-panel__info__label_member-stats-for-period">Total usage time</div>
            <div class="ed-panel__info__value ed-panel__info__value_member-stats-for-period">87 hours 35 minutes 52 seconds</div>"""

        # TODO realized these repeat, might have to use find_all and loop through them instead
        try:
            _ = soup.find_all("div", {"class": "ed-panel__info__value ed-panel__info__value_member-stats-for-period"},)[
                0
            ].text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_lifetime_stats_distance_traveled(self, soup):
        """Extract lifetime stats for distance traveled from profile soup"""

        # TODO Currently returns nbsp between number and miles: 653.1&nbsp;miles
        try:
            _ = soup.find_all("div", {"class": "ed-panel__info__value ed-panel__info__value_member-stats-for-period"},)[
                1
            ].text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_lifetime_stats_gas_saved(self, soup):
        """Extract lifetime stats for gas saved from profile soup"""

        # TODO Currently returns nbsp between number and gallons: 27.1&nbsp;gallons
        try:
            _ = soup.find_all("div", {"class": "ed-panel__info__value ed-panel__info__value_member-stats-for-period"},)[
                2
            ].text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_lifetime_stats_co2_reduced(self, soup):
        """Extract lifetime stats for co2 reduced from profile soup"""

        # TODO Currently contains nbsp between number and lbs: 530.5&nbsp;lbs
        try:
            _ = soup.find_all("div", {"class": "ed-panel__info__value ed-panel__info__value_member-stats-for-period"},)[
                3
            ].text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_first_name(self, soup):
        """Extract profile first name from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_firstname"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_last_name(self, soup):
        """Extract profile last name from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_lastname"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_user_name(self, soup):
        """Extract profile username from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_username"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_date_of_birth(self, soup):
        """Extract date of birth from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_date-of-birth"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_gender(self, soup):
        """Extract gender from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_gender"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_email(self, soup):
        """Extract email from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_email"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_phone_number(self, soup):
        """Extract phone number from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_phone-number"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_member_since(self, soup):
        """Extract profile member since from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_member-since"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_profile_bike_angel_since(self, soup):
        """Extract profile bike angel since from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_bike-angel-since"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_last_trip_dates(self, soup):
        """Extract last trip dates from profile soup"""

        _dates = []
        try:
            # 'August 11th, 2019 12:47 PM'
            _ = soup.find("div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_start-date"},).text
            _dates.append(_)

            _ = soup.find("div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_end-date"},).text
            _dates.append(_)
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _dates = (None, None)
        return _dates

    def from_soup_get_last_trip_stations(self, soup):
        """Extract last trip stations from profile soup"""

        _stations = []
        try:
            # '10 Ave & W 28 St'
            _ = soup.find(
                "div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_start-station-name"},
            ).text
            _stations.append(_)

            # TODO cannot currently test missing end station in profile, try/except will have to catch
            _ = soup.find(
                "div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_end-station-name"},
            ).text
            _stations.append(_)
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _stations = (None, None)
        return _stations

    def from_soup_get_last_trip_time(self, soup):
        """Extract last trip trip from profile soup"""

        try:
            # 16 minutes 10 seconds
            _ = soup.find(
                "div", {"class": "ed-panel__info__value ed-panel__info__value_summary ed-panel__info__value_last-trip"},
            ).text

        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_last_trip_bike_angels_points(self, soup):
        """Extract last trip bikeagels points from profile soup"""

        try:
            # 16 minutes 10 seconds
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_last-trip-bike-angel"},).text

        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_ba_points_current(self, soup):
        """Extract bikeangels current points total from profile soup"""

        try:
            # extract digits from string '70 points (August)'
            _ = int(soup.find("div", {"class": "ed-panel__info__value__part"}).text.split(" ")[0])
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_ba_points_annual(self, soup):
        """Extract bikeangles annual points total from profile soup"""

        try:
            _ = int(
                soup.find("div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_1"},).text.split(
                    " "
                )[0]
            )
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_ba_points_lifetime(self, soup):
        """Extract bikeangles lifetime points total from profile soup"""

        try:
            _ = int(
                soup.find("div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_2"},).text.split(
                    " "
                )[0]
            )
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_bike_key_number(self, soup):
        """Extract bike key number from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_key-number"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_bike_key_status(self, soup):
        """Extract bike key status from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_key-status"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_current_status(self, soup):
        """Extract current membership status from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_subscription-status"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_current_type(self, soup):
        """Extract current membership type from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_subscription-type"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_current_expiration(self, soup):
        """Extract current membership expiration from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_subscription-end-date"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_next_status(self, soup):
        """Extract next membership status from profile soup"""

        try:
            _ = soup.find(
                "div", {"class": "ed-panel__info__value ed-panel__info__value_renewed-subscription-status"},
            ).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_next_type(self, soup):
        """Extract next membership type from profile soup"""

        try:
            _ = soup.find(
                "div", {"class": "ed-panel__info__value ed-panel__info__value_renewed-subscription-type"},
            ).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_next_start(self, soup):
        """Extract next membership start from profile soup"""

        try:
            _ = soup.find(
                "div", {"class": "ed-panel__info__value ed-panel__info__value_renewed-subscription-start-date"},
            ).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_membership_next_expiration(self, soup):
        """Extract next membership expiration from profile soup"""

        try:
            _ = soup.find(
                "div", {"class": "ed-panel__info__value ed-panel__info__value_renewed-subscription-end-date"},
            ).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_billing_summary_next_billing_date(self, soup):
        """Extract billing summary next billing date from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_period"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_billing_summary_current_balance(self, soup):
        """Extract billing summary current balance from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value ed-panel__info__value_amount"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def from_soup_get_billing_info_postal_code(self, soup):
        """Extract billing postal code from profile soup"""

        try:
            _ = soup.find("div", {"class": "ed-panel__info__value__part ed-panel__info__value__part_postalCode"},).text
        except Exception as e:
            log.warn("soup find got exception {}".format(e))
            _ = None
        return _

    def gen_trips_url_num(self, page_num):
        """generate url for individual trip page"""

        _ = "{}?pageNumber={}".format(self.trips_url, page_num)
        log.debug("Trips page url {}".format(_))
        return _

    def get_trips_links(self):
        """Extract trips link from profile and number of last trips page. Will Get request and process account data from profile page if soup_profile does not exist."""

        if not self.soup_profile:
            self.get_account_soup()
        soup = self.soup_profile

        self.trips_link = soup.find(
            "li", {"class": "ed-profile-menu__link ed-profile-menu__link_trips ed-profile-menu__link_level1"},
        ).a.get("href")
        log.info("Trips link {}".format(self.trips_link))
        self.trips_url = "{}{}".format(self.url_member_base, self.trips_link)
        log.info("Trips base {}".format(self.trips_url))

        # extract unique account id from trip link, this is different than bike key
        # TODO test account with multiple riders?
        self.account["id"].append(self.trips_link.split("/")[-1])

        soup = self.get_trips_soup()

        self.trips_last = int(
            soup.find(
                "a",
                {"class": "ed-paginated-navigation__pages-group__link_last ed-paginated-navigation__pages-group__link"},
            )
            .get("href")
            .split("=")[1]
        )
        log.info("Total number of trips pages {}".format(self.trips_last))

    def get_trips_soup(self, page_num=1):
        """Request trip by by number and return parsed html as beautiful soup object. Lower page numbers are more recent, starting at zero."""

        page_url = self.gen_trips_url_num(page_num)
        log.debug("GET trips page url {}".format(page_url))
        res = self.s.get(page_url, headers=dict(referer=self.url_profile))

        if res.status_code == requests.codes["ok"]:
            log.debug("GET trips page {} PASS".format(page_num))
            self.url_last = page_url
        else:
            log.debug("GET trips page {} FAIL".format(page_num))
            return False

        soup = BeautifulSoup(res.content, "html5lib")
        return soup

    def get_trips_loop(self, last_page=0):
        """Get trip pages starting at most recent up to last_page.

        If last_page not provided, will collect all pages. The last_page is extracted from footer by get_trips_links"""

        if not hasattr("self", "trips_last"):
            self.get_trips_links()

        if 0 == last_page:
            last_page = self.trips_last

        log.info("Grabbing trips from 1 to {}".format(last_page))
        for tp in range(1, last_page + 1):
            log.info("get trips page {}".format(tp))
            soup = self.get_trips_soup(tp)
            trips = self.extract_trip_data(soup)
            self.trips.extend(trips)

        log.info("total trips {}".format(len(self.trips)))

    def extract_trip_data(self, soup):
        """Extracts trip data from a beautiful soup object and returns trip object"""

        table = soup.find("table", {"class": "ed-html-table ed-html-table_trip"})
        log.debug("Found trip table: {}".format(table))

        trips = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            log.debug("found trip table row has {} cells".format(len(cells)))
            # first tr row is th header instead of td data cells
            if len(cells) < 1:
                # skip th header row or other possibly empty row
                log.debug("skipping short trip table row")
                continue

            _ = cells[0].find_all("div")
            start_station = _[0].text.strip()
            start_time = _[1].text.strip()

            # bikeangles points always return zero even if disabled
            try:
                start_points = int(_[2].text.strip())
            except:
                start_points = 0

            _ = cells[1].find_all("div")
            end_station = _[0].text.strip()
            end_time = _[1].text.strip()

            # bikeangles points always return zero even if disabled
            try:
                end_points = int(_[2].text.strip())
            except:
                end_points = 0

            duration = cells[2].get_text().strip()
            billed = cells[3].get_text().strip()
            try:
                points = int(cells[4].get_text().strip().split(" ")[0])
            except:
                points = 0

            trip = (
                start_station,
                end_station,
                start_time,
                end_time,
                start_points,
                end_points,
                points,
                billed,
                duration,
            )
            trips.append(trip)

        return trips

    def write_stations_json(self, file):
        """Write stations object out to file in json format"""

        log.info("writing stations json to {}".format(file))
        with open(file, "w") as f:
            f.write(json.dumps(self.stations, indent=2))

    def write_account_json(self, file):
        """Writes account object with profile data out to file in json format"""

        log.info("writing account json to {}".format(file))
        with open(file, "w") as f:
            f.write(json.dumps(self.account, indent=2))

    def write_trips_json(self, file):
        """Writes trip object out to file in json format"""

        log.info("writing trips json to {}".format(file))
        with open(file, "w") as f:
            f.write(json.dumps(self.trips, indent=2))

    def write_trips_full_json(self, file):
        """Writes trips_full object out to file in json format"""

        log.info("writing trips full json to {}".format(file))
        with open(file, "w") as f:
            f.write(json.dumps(self.trips_full, indent=2))

    def write_trips_csv(self, file):
        """Writes trips object out to file in CSV format"""

        import csv

        log.info("writing trips csv to {}".format(file))
        with open(file, "w") as f:
            writer = csv.writer(f)
            writer.writerow(self.csv_header)
            writer.writerows(self.trips)

    def write_trips_full_csv(self, file):
        """Calls hydrate_trips if trips_full missing, then writes out to CSV on filesystem"""

        if not self.trips_full:
            self.hydrate_trips()
        import csv

        log.info("writing trips csv to {}".format(file))
        with open(file, "w") as f:
            writer = csv.writer(f)
            writer.writerow(self.csv_header_full)
            writer.writerows(self.trips_full)

    def load_json(self, ts):
        """Load a set of cached trips, account, and stations objects from filesystem given a timestamp string"""

        self.ts = ts

        file = "{}/cb_trips_{}.json".format(self.data_dir, self.ts)
        log.debug("loading trips from {}".format(file))
        with open(file, "r", encoding="utf-8") as f:
            self.trips = json.load(f)

        file = "{}/cb_account_{}.json".format(self.data_dir, self.ts)
        log.debug("loading account from {}".format(file))
        with open(file, "r", encoding="utf-8") as f:
            self.account = json.load(f)

        file = "{}/cb_stations_{}.json".format(self.data_dir, self.ts)
        log.debug("loading stations from {}".format(file))
        with open(file, "r", encoding="utf-8") as f:
            self.stations = json.load(f)

    def get_stations(self, file=None):
        """Create stations object from net or load from cached file"""

        if file:
            log.debug("loading stations from {}".format(file))
            with open(file, "r", encoding="utf-8") as f:
                self.stations = json.load(f)
        else:
            log.debug("getting stations from {}".format(self.url_stations))
            r = self.s.get(self.url_stations, timeout=self.t)
            self.stations = r.json()

    def hydrate_trips(self, datestring=True, locations=True):
        """given a citibike trips object, add all the data for the full report"""

        # TODO making zipcode and bikeangels optional makes us question what a "full report" means
        log.info("hydrating trip data")
        self.trips_full = []
        for trip in self.trips:
            log.debug("start station {}".format(trip[2]))

            # Starting station exceptions happen when stations don't exist anymore
            # "W 17 St & 9 Ave" is in history but cannot lookup in stations.json
            try:
                start_station = self.station_by_name(trip[2])

                start_id = start_station["properties"]["station_id"]
                start_terminal = start_station["properties"]["terminal"]
                # TODO named tuples would have avoided this bug
                dollars = self.dollars_to_float(trip[7])
                # TODO add iso8601 duration format https://en.wikipedia.org/wiki/ISO_8601#Time_intervals
                seconds = self.str_to_secs(trip[8])

                start_dt = datetime.datetime.strptime(trip[0], DTS)
                # TODO python3 doesn't need pytz anymore? https://stackoverflow.com/questions/2150739/iso-time-iso-8601-in-python
                start_dtz = TZ.localize(start_dt)
                start_epoch = int(start_dtz.timestamp())
                # TODO add iso8601 datetime format https://en.wikipedia.org/wiki/ISO_8601
                start_iso8601 = start_dtz.isoformat()

                start_loc = start_station["geometry"]["coordinates"]
                start_lon = start_station["geometry"]["coordinates"][0]
                start_lat = start_station["geometry"]["coordinates"][1]
            except:
                start_id = "-"
                start_terminal = "-"

                start_dt = datetime.datetime.strptime(trip[0], DTS)
                start_dtz = TZ.localize(start_dt)
                start_epoch = int(start_dtz.timestamp())

                start_loc = "-"
                start_lon = "-"
                start_lat = "-"

            # Ending station exceptions happen when trips are not closed properly
            # bikes not returned, dock malfunctions, whatever
            try:
                end_station = self.station_by_name(trip[3])
                end_id = end_station["properties"]["station_id"]
                end_terminal = end_station["properties"]["terminal"]
                end_loc = end_station["geometry"]["coordinates"]
                end_lon = end_station["geometry"]["coordinates"][0]
                end_lat = end_station["geometry"]["coordinates"][1]
                end_dt = datetime.datetime.strptime(trip[0], DTS)
                end_dtz = TZ.localize(end_dt)
                end_epoch = int(end_dtz.timestamp())
                end_iso8601 = end_dtz.isoformat()
                dollars = self.dollars_to_float(trip[7])
                seconds = self.str_to_secs(trip[8])
            except:
                end_station = "-"
                end_id = "-"
                end_terminal = "-"
                end_loc = "-"
                end_lon = "-"
                end_lat = "-"
                end_dt = "-"
                end_dtz = "-"
                end_iso8601 = "-"
                dollars = 0.0
                seconds = 0

            row = []
            row.append(self.account["id"][0])
            row.append(self.ts)
            row.extend(trip)
            row.extend(
                [
                    start_id,
                    end_id,
                    start_terminal,
                    end_terminal,
                    start_lon,
                    start_lat,
                    end_lon,
                    end_lat,
                    dollars,
                    seconds,
                    start_epoch,
                    end_epoch,
                    start_iso8601,
                    end_iso8601,
                ]
            )
            self.trips_full.append(row)
        return self.trips_full

    def str_to_secs(self, st):
        """convert string of minutes and seconds to seconds"""

        # TODO need to support '1 h 26 min 55 s'
        m, sm, s, ss = st.split(" ")
        secs = int(s) + int(m) * 60
        return secs

    def dollars_to_float(self, st):
        """convert us currency string to float"""

        dollars = float(st[2:])
        return dollars

    def loc_by_name(self, name):
        """Search stations object by station name and return station object"""

        try:
            station = [_ for _ in self.stations["features"] if name == _["properties"]["name"]]
            log.debug("searching for station {} found {}".format(name, station))
            return station[0]
        except:
            log.debug("searching for station {} found None")
            return None

    def station_by_name(self, name):
        """Search stations object by station name and return station object"""

        try:
            station = [_ for _ in self.stations["features"] if name == _["properties"]["name"]]
            log.debug("searching for station {} found {}".format(name, station))
            return station[0]
        except:
            log.debug("Exception: searching for station {} found None".format(name))
            return None

    def station_by_location(self, location):
        """Search stations object by location coordinates and return station object"""

        try:
            station = [_ for _ in self.stations["features"] if location == _["geometry"]["coordinates"]]
            log.debug("searching for location {} found {}".format(location, station))
            return station[0]
        except:
            log.debug("searching for location {} found None")
            return None

    def station_by_id(self, id):
        """Search stations object by station id and return station object"""

        try:
            station = [_ for _ in self.stations["features"] if _["properties"]["station_id"] == id]
            log.debug("searching for station_id {} found {}".format(id, station))
            return station[0]
        except:
            log.debug("searching for station_id {} found None".format(id))
            return None

    def all_routes(self):
        """Return array of route start terminal and end terminal pairs from trips object"""

        routes = [(x[2], x[3]) for x in self.trips]
        return routes
