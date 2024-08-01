"""

The Sky module abstracts solar system objects, celestial bodies, and artificial satellites into a SkyObject data structure.
These classes are used to perform object searches (e.g. JPL HORIZON, SIMBAD, etc.) and determine object observability.

"""

from astropy.visualization import astropy_mpl_style
import matplotlib.pyplot as plt
import logging
import re
import urllib.request as urllib
from io import BytesIO
from zipfile import ZipFile
import ephem
from astropy.coordinates import SkyCoord, Angle, AltAz, get_sun
from astropy.time import Time
from astroquery.simbad import Simbad
import astropy.units as u
import datetime
import math
import collections
import ch  # callhorizons module customized
import numpy as np
import matplotlib

matplotlib.use("Agg")  # don't need display
plt.style.use(astropy_mpl_style)

# defines a sky object data structure
SkyObject = collections.namedtuple("SkyObject", "id name type ra dec vmag tle1 tle2")
SkyObject.__new__.__defaults__ = (None,) * len(SkyObject._fields)


class SolarSystem:
    """Class to manage finding and plotting solar system objects"""

    def __init__(self, ixchel):
        self.logger = logging.getLogger("SolarSystem")
        self.ixchel = ixchel
        self.config = ixchel.config

    def plot(self, solarSystemObject):
        """Plots the visibility of a solar system object, sending the result to Slack

        Args:
            solarSystemObject (_type_): _description_
        """
        # get current coordinates
        c = SkyCoord(solarSystemObject.ra, solarSystemObject.dec, unit=(u.hour, u.deg))
        # look 24 hours into the future
        now = Time(datetime.datetime.utcnow(), scale="utc")
        oneDay = np.linspace(0, 24, 1000) * u.hour
        times_now_to_tomorrow = now + oneDay
        frame_now_to_tomorrow = AltAz(
            obstime=times_now_to_tomorrow, location=self.ixchel.telescope.earthLocation
        )
        object_altaz_now_to_tomorrow = c.transform_to(frame_now_to_tomorrow)
        sun_altaz_now_to_tomorrow = get_sun(times_now_to_tomorrow).transform_to(
            frame_now_to_tomorrow
        )
        plt.scatter(
            oneDay,
            object_altaz_now_to_tomorrow.alt,
            c=object_altaz_now_to_tomorrow.az,
            label=solarSystemObject.name,
            lw=0,
            s=20,
            cmap="viridis",
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -0 * u.deg,
            color="0.5",
            zorder=0,
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -18 * u.deg,
            color="k",
            zorder=0,
        )
        plt.colorbar().set_label("Azimuth [deg]")
        plt.legend(loc="best")
        plt.xlim(0, 24)
        plt.xticks(np.arange(13) * 2)
        plt.ylim(0, 90)
        plt.xlabel("Hours [from now]")
        plt.ylabel("Altitude [deg]")
        plot_png_file_path = (
            self.config.get("misc", "plot_file_path", "plot.png") + "plot.png"
        )
        plt.savefig(plot_png_file_path, bbox_inches="tight", format="png")
        plt.close()
        self.ixchel.slack.send_file(
            plot_png_file_path, "%s Visibility" % solarSystemObject.name
        )

    def find(
        self, search_string
    ):  # this is a terrible scraping hack, but it's proven and comprehensive
        """Finds a solar system object by searching through JPL's Horizons System.

        Args:
            search_string (string): solar system identifier to search for

        Returns:
            list[SkyObject]: all matching solar system objects, in SkyObject form
        """
        solarSystemObjects = []
        suffix = ""  # set to * to make the searches wider by default
        # two passes, one for major (and maybe small) and one for (only) small bodies
        search_strings = [search_string + suffix, search_string + suffix + ";"]
        # list of matches
        objects = []
        for repeat in range(0, 2):
            # user JPL Horizons batch to find matches
            f = urllib.urlopen(
                'https://ssd.jpl.nasa.gov/horizons_batch.cgi?batch=l&COMMAND="%s"'
                % urllib.quote(search_strings[repeat].upper())
            )
            output = f.read().decode()  # the whole enchilada
            lines = output.splitlines()  # line by line
            # no matches? go home
            if re.search("No matches found", output):
                self.logger.warning(
                    "No matches found in JPL Horizons for %s."
                    % search_strings[repeat].upper()
                )
            elif re.search("Target body name:", output):
                self.logger.info(
                    "Single match found in JPL Horizons for %s."
                    % search_strings[repeat].upper().replace(suffix, "")
                )
                # just one match?
                # if major body search (repeat = 0), ignore small body results
                # if major body search, grab integer id
                if repeat == 0:
                    if re.search("Small-body perts:", output):
                        continue
                    match = re.search(
                        r"Target body name:\s[a-zA-Z]+\s\((\d+)\)", output
                    )
                    if match:
                        objects.append(match.group(1))
                    else:
                        self.logger.error(
                            "Error. Could not parse id for single match major body (%s)."
                            % search_strings[repeat].upper().replace(suffix, "")
                        )
                else:
                    # user search term is unique, so use it!
                    objects.append(search_strings[repeat].upper().replace(suffix, ""))
            elif repeat == 1 and re.search("Matching small-bodies", output):
                self.logger.info(
                    "Multiple small bodies found in JPL Horizons for %s."
                    % search_strings[repeat].upper()
                )
                # Matching small-bodies:
                #
                #    Record #  Epoch-yr  Primary Desig  >MATCH NAME<
                #    --------  --------  -------------  -------------------------
                #          4             (undefined)     Vesta
                #      34366             2000 RP36       Rosavestal
                match_count = 0
                for line in lines:
                    # look for small body list
                    match = re.search(r"^-?\d+", line.strip())
                    # parse out the small body parameters
                    if match:
                        match_count += 1
                        record_number = line[0:12].strip()
                        epoch_yr = line[12:22].strip()
                        primary_desig = line[22:37].strip()
                        match_name = line[37 : len(line)].strip()
                        # add semicolon for small body search_strings
                        objects.append(record_number + ";")
                # check our parse job
                match = re.search(r"(\d+) matches\.", output)
                if match:
                    if int(match.group(1)) != match_count:
                        self.logger.error("Multiple JPL small body parsing error!")
                    else:
                        self.logger.info("Multiple JPL small body parsing successful!")
            elif repeat == 0 and re.search("Multiple major-bodies", output):
                self.logger.info(
                    "Multiple major bodies found in JPL Horizons for %s."
                    % search_strings[repeat].upper()
                )
                # Multiple major-bodies match string "50*"
                #
                #  ID#      Name                               Designation  IAU/aliases/other
                #  -------  ---------------------------------- -----------  -------------------
                #      501  Io                                              JI
                #      502  Europa                                          JII
                match_count = 0
                for line in lines:
                    search_string = line.strip()
                    # look for major body list
                    match = re.search(r"^-?\d+", search_string)
                    # parse out the major body parameters
                    if match:
                        match_count += 1
                        record_number = line[0:9].strip()
                        # negative major bodies are spacecraft,etc. Skip those!
                        if int(record_number) >= 0:
                            name = line[9:45].strip()
                            designation = line[45:57].strip()
                            other = line[57 : len(line)].strip()
                            # NO semicolon for major body search_strings
                            objects.append(record_number)
                # check our parse job
                match = re.search(r"Number of matches =([\s\d]+).", output)
                if match:
                    if int(match.group(1)) != match_count:
                        self.logger.error("Multiple JPL major body parsing error!")
                    else:
                        self.logger.info("Multiple JPL major body parsing successful!")
        # calculate RA/DEC
        start = datetime.datetime.utcnow()
        end = start + datetime.timedelta(seconds=60)
        for obj in objects:
            try:
                result = ch.query(obj.upper(), smallbody=False)
                result.set_epochrange(
                    start.strftime("%Y/%m/%d %H:%M"),
                    end.strftime("%Y/%m/%d %H:%M"),
                    "1m",
                )
                result.get_ephemerides(self.config.get("telescope", "code"))
                ra = Angle("%fd" % result["RA"][0]).to_string(unit=u.hour, sep=":")
                dec = Angle("%fd" % result["DEC"][0]).to_string(unit=u.degree, sep=":")
                solarSystemObject = SkyObject(
                    id=obj.upper(),
                    name=result["targetname"][0],
                    type="Solar System",
                    ra=ra,
                    dec=dec,
                    vmag="%.1f" % result["V"][0],
                )
                solarSystemObjects.append(solarSystemObject)
            except Exception as e:
                self.logger.error(
                    "Error. Could not determine RA/DEC of small body. Exception (%s)."
                    % e
                )
                pass
        return solarSystemObjects


class Coordinate:
    """Class to manage plotting coordinates from exisint SkyObject(s)"""

    def __init__(self, ixchel):
        self.logger = logging.getLogger("Coordinate")
        self.ixchel = ixchel
        self.config = ixchel.config

    def plot(self, ra, dec):
        """Plos the given coordinate, sending the result to Slack

        Args:
            ra (_type_): _description_
            dec (_type_): _description_
        """
        # get current coordinates
        c = SkyCoord(ra, dec, unit=(u.hour, u.deg))
        # look 24 hours into the future
        now = Time(datetime.datetime.utcnow(), scale="utc")
        oneDay = np.linspace(0, 24, 1000) * u.hour
        times_now_to_tomorrow = now + oneDay
        frame_now_to_tomorrow = AltAz(
            obstime=times_now_to_tomorrow, location=self.ixchel.telescope.earthLocation
        )
        object_altaz_now_to_tomorrow = c.transform_to(frame_now_to_tomorrow)
        sun_altaz_now_to_tomorrow = get_sun(times_now_to_tomorrow).transform_to(
            frame_now_to_tomorrow
        )
        plt.scatter(
            oneDay,
            object_altaz_now_to_tomorrow.alt,
            c=object_altaz_now_to_tomorrow.az,
            label="%s / %s" % (ra, dec),
            lw=0,
            s=20,
            cmap="viridis",
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -0 * u.deg,
            color="0.5",
            zorder=0,
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -18 * u.deg,
            color="k",
            zorder=0,
        )
        plt.colorbar().set_label("Azimuth [deg]")
        plt.legend(loc="best")
        plt.xlim(0, 24)
        plt.xticks(np.arange(13) * 2)
        plt.ylim(0, 90)
        plt.xlabel("Hours [from now]")
        plt.ylabel("Altitude [deg]")
        plot_png_file_path = (
            self.config.get("misc", "plot_file_path", "plot.png") + "plot.png"
        )
        plt.savefig(plot_png_file_path, bbox_inches="tight", format="png")
        plt.close()
        self.ixchel.slack.send_file(
            plot_png_file_path, "Celestial Coordinates Visibility"
        )


class Celestial:
    """Class to manage finding and plotting celestial objects"""

    def __init__(self, ixchel):
        self.logger = logging.getLogger("Celestial")
        self.ixchel = ixchel
        self.config = ixchel.config
        Simbad.add_votable_fields("fluxdata(V)")

    def plot(self, celestialObject):
        """Plots a given celestial object, sending the result to Slack

        Args:
            celestialObject (_type_): _description_
        """
        # get current coordinates
        c = SkyCoord(celestialObject.ra, celestialObject.dec, unit=(u.hour, u.deg))
        # look 24 hours into the future
        now = Time(datetime.datetime.utcnow(), scale="utc")
        oneDay = np.linspace(0, 24, 1000) * u.hour
        times_now_to_tomorrow = now + oneDay
        frame_now_to_tomorrow = AltAz(
            obstime=times_now_to_tomorrow, location=self.ixchel.telescope.earthLocation
        )
        object_altaz_now_to_tomorrow = c.transform_to(frame_now_to_tomorrow)
        sun_altaz_now_to_tomorrow = get_sun(times_now_to_tomorrow).transform_to(
            frame_now_to_tomorrow
        )
        plt.scatter(
            oneDay,
            object_altaz_now_to_tomorrow.alt,
            c=object_altaz_now_to_tomorrow.az,
            label=celestialObject.name,
            lw=0,
            s=20,
            cmap="viridis",
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -0 * u.deg,
            color="0.5",
            zorder=0,
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -18 * u.deg,
            color="k",
            zorder=0,
        )
        plt.colorbar().set_label("Azimuth [deg]")
        plt.legend(loc="best")
        plt.xlim(0, 24)
        plt.xticks(np.arange(13) * 2)
        plt.ylim(0, 90)
        plt.xlabel("Hours [from now]")
        plt.ylabel("Altitude [deg]")
        plot_png_file_path = (
            self.config.get("misc", "plot_file_path", "plot.png") + "plot.png"
        )
        plt.savefig(plot_png_file_path, bbox_inches="tight", format="png")
        plt.close()
        self.ixchel.slack.send_file(
            plot_png_file_path, "%s Visibility" % celestialObject.name
        )

    def find(self, search_string):
        """Searches Simbad for the given celestial object search string

        Args:
            search_string (string): Simbad query

        Returns:
            list[SkyObject]: Simbad query results in SkyObject form
        """
        celestials = []
        results = Simbad.query_object(search_string.upper().replace("*", ""))
        if results is not None:
            for row in range(0, len(results)):
                # why doesn't Simbad always return utf8?
                try:
                    celestial = SkyObject(
                        id=results["MAIN_ID"][row],
                        name=results["MAIN_ID"][row].decode().replace(" ", ""),
                        type="Celestial",
                        ra=results["RA"][row].replace(" ", ":"),
                        dec=results["DEC"][row].replace(" ", ":"),
                        vmag="%.1f" % results["FLUX_V"][row],
                    )
                except Exception:
                    celestial = SkyObject(
                        id=results["MAIN_ID"][row],
                        name=results["MAIN_ID"][row].replace(" ", ""),
                        type="Celestial",
                        ra=results["RA"][row].replace(" ", ":"),
                        dec=results["DEC"][row].replace(" ", ":"),
                        vmag="%.1f" % results["FLUX_V"][row],
                    )
                celestials.append(celestial)
        return celestials


class Satellite:
    """Class to manage loading, finding, and plotting satellites"""

    def __init__(self, ixchel):
        self.logger = logging.getLogger("Satellite")
        self.ixchel = ixchel
        self.config = ixchel.config
        self.db = self.buildSatelliteDatabase()
        # config the pyephem observer
        self.observer = ephem.Observer()
        self.observer.lat, self.observer.lon = "%s" % self.config.get(
            "telescope", "latitude", "0.0"
        ), "%s" % self.config.get("telescope", "longitude", "0.0")

    def buildSatelliteDatabase(self):
        """Loads satellites from the data sets linked `norad_sat_urls` in the
        config file. All pages should be in TLE format.

        Returns:
            list[SkyObjects]: all the collected satellites in SkyObject form
        """
        self.logger.info("Loading satellite TLE into database...")
        norad_sats_urls = self.config.get("misc", "norad_sat_urls").split("\n")
        db = []
        for url in norad_sats_urls:
            # grab NORAD geosat data
            # if it's a zipped file, unzip first!
            if re.search("zip$", url):
                zipfile = ZipFile(BytesIO(urllib.urlopen(url).read()))
                sats = zipfile.open(zipfile.namelist()[0]).readlines()
            else:
                try:
                    sats = urllib.urlopen(url).readlines()
                except Exception as e:
                    self.logger.error(
                        "Failed to open satellite database (%s). Exception (%s)."
                        % (url, e)
                    )
                    continue
            # clean it up
            sats = [item.strip() for item in sats]
            # create an array of name, tle1, and tle2
            sats = [
                ((sats[i]).upper(), sats[i + 1], sats[i + 2])
                for i in range(0, len(sats) - 2, 3)
            ]
            # add sats to norad database
            db += sats
        self.logger.info("Loaded %d satellite TLE(s) into the database." % len(db))
        return db

    def plot(self, satellite):
        """Plots a given satellite from the database, sending the result to Slack

        Args:
            satellite (_type_): _description_
        """
        now = Time(datetime.datetime.utcnow(), scale="utc")
        oneDay = np.linspace(0, 24, 1000) * u.hour
        times_now_to_tomorrow = now + oneDay
        frame_now_to_tomorrow = AltAz(
            obstime=times_now_to_tomorrow, location=self.ixchel.telescope.earthLocation
        )
        sun_altaz_now_to_tomorrow = get_sun(times_now_to_tomorrow).transform_to(
            frame_now_to_tomorrow
        )
        alt = []
        az = []
        sat_ephem = ephem.readtle(satellite.id, satellite.tle1, satellite.tle2)
        for time_now_to_tomorrow in times_now_to_tomorrow:
            self.observer.date = time_now_to_tomorrow.tt.datetime
            sat_ephem.compute(self.observer)
            alt.append(math.degrees(float(repr(sat_ephem.alt))))
            az.append(math.degrees(float(repr(sat_ephem.az))))
        plt.scatter(oneDay, alt, c=az, label=satellite.name, lw=0, s=20, cmap="viridis")
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -0 * u.deg,
            color="0.5",
            zorder=0,
        )
        plt.fill_between(
            oneDay.to("hr").value,
            0,
            90,
            sun_altaz_now_to_tomorrow.alt < -18 * u.deg,
            color="k",
            zorder=0,
        )
        plt.colorbar().set_label("Azimuth [deg]")
        plt.legend(loc="best")
        plt.xlim(0, 24)
        plt.xticks(np.arange(13) * 2)
        plt.ylim(0, 90)
        plt.xlabel("Hours [from now]")
        plt.ylabel("Altitude [deg]")
        plot_png_file_path = (
            self.config.get("misc", "plot_file_path", "plot.png") + "plot.png"
        )
        plt.savefig(plot_png_file_path, bbox_inches="tight", format="png")
        plt.close()
        self.ixchel.slack.send_file(
            plot_png_file_path, "%s Visibility" % satellite.name
        )

    def find(self, search_string):
        """Find a satellite in the existing, loaded database

        Args:
            search_string (string): the satellite identifier to search for

        Returns:
            list[SkyObject]: all satellites matching the search string in SkyObject form
        """
        satellites = []
        for sat in self.db:
            # if re.search(r'\*$', search_string):
            #     got_match = (sat[0].find(search_string.upper().replace('*', '')) >= 0)
            # else:
            #     got_match = (sat[0] == search_string.upper())
            # try always doing a partial search
            got_match = (
                sat[0].find(search_string.upper().replace("*", "").encode()) >= 0
            )
            if got_match:
                name = sat[0]
                tle1 = sat[1]
                tle2 = sat[2]
                sat_ephem = ephem.readtle(name.decode(), tle1.decode(), tle2.decode())
                self.observer.date = datetime.datetime.utcnow()
                sat_ephem.compute(self.observer)
                satellite = SkyObject(
                    id=name,
                    name=name.decode(),
                    type="Satellite",
                    tle1=tle1,
                    tle2=tle2,
                    ra="%s" % sat_ephem.ra,
                    dec="%s" % sat_ephem.dec,
                )
                satellites.append(satellite)
        return satellites


class Sky:
    """Holds the list of all objects that we've loaded; including Satellites,
    Celestial, Coordinate, and SolarSystem objects.
    """

    # current object list
    sky_objects = []

    def __init__(self, ixchel):
        self.logger = logging.getLogger("Sky")
        self.ixchel = ixchel
        self.config = ixchel.config
