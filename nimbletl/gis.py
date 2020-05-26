"""Helper functions for geocoding and coordinate conversions."""

from builtins import enumerate
import requests
import json


def get_RDXY(postcode, huisnummer):
    """
    Fetches X, Y Rijksdriehoek coordinates from BAG.

    postcode:   Dutch zipcode in format '1234AB'
    huisnmmmer: house number, without any additions

    https://basisregistraties.arcgisonline.nl/arcgis/rest/services/BAG/
    """

    URL = f"https://basisregistraties.arcgisonline.nl/arcgis/rest/services/BAG/BAGv2/MapServer/0/query?where=huisnummer%3D%27{huisnummer}%27+AND+postcode+%3D+%27{postcode}%27&text=&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&relationParam=&outFields=&returnGeometry=true&returnTrueCurves=false&maxAllowableOffset=&geometryPrecision=&outSR=28992&having=&returnIdsOnly=false&returnCountOnly=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&returnZ=false&returnM=false&gdbVersion=&historicMoment=&returnDistinctValues=false&resultOffset=&resultRecordCount=&queryByDistance=&returnExtentOnly=false&datumTransformation=&parameterValues=&rangeValues=&quantizationParameters=&featureEncoding=esriDefault&f=pjson"
    get_ = requests.get(URL.format(postcode=postcode, huisnummer=str(huisnummer)))
    try:
        return get_.json()["features"][0]["geometry"]
    except (KeyError, IndexError):
        return None


# Can't access API reference, so don't know how to code proper POST request
#
# def test(postcode, huisnummer):
#     URL = "https://basisregistraties.arcgisonline.nl/arcgis/rest/services/BAG/BAGv2/MapServer/0/query"
#     query = {'postcode': postcode,
#     'huisnummer': huisnummer,
#     'GeometryType': 'esriGeometryEnvelope',
#     'outSR': '28992',
#     'featureEncoding': 'esriDefault',
#     'f': 'pjson'
#     }
#     print(json.dumps(query))
#     response = requests.request('POST', URL, data=json.dumps(query))
# print(response.json())



class RDWGS84Converter(object):
    """
    The formulas in this class were based on a white paper by ing. F.H. Schreutelkamp from "Stichting De Koepel" and
    ir. G.L. Strang van Hees, former scholar at TU Delft.
    Unfortunately, as of January 1st 2014, the foundation "De Koepel" has halted all their activities and suspended their
    website. As the original article can no longer be found on the website, I've made sure to host 
    `a backup of it <http://media.thomasv.nl/2015/07/Transformatieformules.pdf>`_ (in Dutch). Please consult this white
    paper for the origin of the coefficients used below.
    I take no credit for the formulas used, all I have done was convert the formulas into an easy to work with Python
    class for usage in other projects. All credit for the formulas go to F.H. Schreutelkamp and G.L. Strang van Hees.
    """

    x0 = 155000
    y0 = 463000
    phi0 = 52.15517440
    lam0 = 5.38720621

    # Coefficients or the conversion from RD to WGS84
    Kp = [0, 2, 0, 2, 0, 2, 1, 4, 2, 4, 1]
    Kq = [1, 0, 2, 1, 3, 2, 0, 0, 3, 1, 1]
    Kpq = [
        3235.65389,
        -32.58297,
        -0.24750,
        -0.84978,
        -0.06550,
        -0.01709,
        -0.00738,
        0.00530,
        -0.00039,
        0.00033,
        -0.00012,
    ]

    Lp = [1, 1, 1, 3, 1, 3, 0, 3, 1, 0, 2, 5]
    Lq = [0, 1, 2, 0, 3, 1, 1, 2, 4, 2, 0, 0]
    Lpq = [
        5260.52916,
        105.94684,
        2.45656,
        -0.81885,
        0.05594,
        -0.05607,
        0.01199,
        -0.00256,
        0.00128,
        0.00022,
        -0.00022,
        0.00026,
    ]
    # Coefficients for the conversion from WGS84 to RD
    Rp = [0, 1, 2, 0, 1, 3, 1, 0, 2]
    Rq = [1, 1, 1, 3, 0, 1, 3, 2, 3]
    Rpq = [
        190094.945,
        -11832.228,
        -114.221,
        -32.391,
        -0.705,
        -2.340,
        -0.608,
        -0.008,
        0.148,
    ]

    Sp = [1, 0, 2, 1, 3, 0, 2, 1, 0, 1]
    Sq = [0, 2, 0, 2, 0, 1, 2, 1, 4, 4]
    Spq = [
        309056.544,
        3638.893,
        73.077,
        -157.984,
        59.788,
        0.433,
        -6.439,
        -0.032,
        0.092,
        -0.054,
    ]

    def from_rd(self, x: int, y: int) -> tuple:
        """
        Converts RD coordinates into WGS84 coordinates
        """
        dx = 1e-5 * (x - self.x0)
        dy = 1e-5 * (y - self.y0)
        latitude = (
            self.phi0
            + sum(
                [
                    v * dx ** self.Kp[i] * dy ** self.Kq[i]
                    for i, v in enumerate(self.Kpq)
                ]
            )
            / 3600
        )
        longitude = (
            self.lam0
            + sum(
                [
                    v * dx ** self.Lp[i] * dy ** self.Lq[i]
                    for i, v in enumerate(self.Lpq)
                ]
            )
            / 3600
        )

        return latitude, longitude

    # https://github.com/thomasvnl/rd-to-wgs84
    def from_wgs84(self, latitude: float, longitude: float) -> tuple:
        """
        Converts WGS84 coordinates into RD coordinates
        """
        dlat = 0.36 * (latitude - self.phi0)
        dlon = 0.36 * (longitude - self.lam0)
        x = self.x0 + sum(
            [
                v * dlat ** self.Rp[i] * dlon ** self.Rq[i]
                for i, v in enumerate(self.Rpq)
            ]
        )
        y = self.y0 + sum(
            [
                v * dlat ** self.Sp[i] * dlon ** self.Sq[i]
                for i, v in enumerate(self.Spq)
            ]
        )

        return x, y
