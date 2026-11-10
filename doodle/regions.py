"""Country code -> world region mapping used for labels and for the game map.

The Quick, Draw! dataset tags every drawing with a 2-letter country code.
We group countries into 9 regions (our own grouping, loosely following UN
subregions, with small tweaks noted below).
"""

REGIONS = [
    # id, short key, display name
    ("north_america", "North America"),
    ("latin_america", "Latin America"),
    ("western_europe", "Western Europe"),
    ("eastern_europe", "Eastern Europe"),
    ("mideast_africa", "Middle East & Africa"),
    ("south_asia", "South Asia"),
    ("east_asia", "East Asia"),
    ("southeast_asia", "Southeast Asia"),
    ("oceania", "Oceania"),
]
REGION_KEYS = [k for k, _ in REGIONS]
REGION_NAMES = [n for _, n in REGIONS]
NUM_REGIONS = len(REGIONS)

_GROUPS = {
    "north_america": "US CA BM PM GL",
    "latin_america": (
        "MX GT BZ SV HN NI CR PA "
        "CU JM HT DO PR TT BS BB LC VC GD AG DM KN AW CW SX KY VI VG TC AI MS MF BL GP MQ "
        "BR AR CL CO PE VE EC BO PY UY GY SR GF FK"
    ),
    "western_europe": (
        "GB IE FR DE NL BE LU CH AT LI MC "
        "ES PT IT GR MT CY AD SM VA "
        "SE NO DK FI IS FO AX JE GG IM GI"
    ),
    # Eastern Europe also holds the Baltics, the Balkans, the Caucasus and
    # Central Asia (post-Soviet / ex-Yugoslav countries) so the group is big
    # enough to learn from.
    "eastern_europe": (
        "RU UA BY PL CZ SK HU RO BG MD EE LV LT "
        "RS HR SI BA ME MK AL XK "
        "GE AM AZ KZ UZ TM TJ KG"
    ),
    "mideast_africa": (
        "TR IL PS SA AE QA KW BH OM YE JO LB SY IQ IR "
        "EG MA DZ TN LY SD EH "
        "ZA NG KE GH ET TZ UG ZW ZM MZ MW MG AO CM CI SN ML BF NE TD CF CD CG GA GQ "
        "ST BJ TG SL LR GN GW GM CV MR SO DJ ER SS RW BI KM SC MU NA BW LS SZ SH RE"
    ),
    "south_asia": "IN PK BD LK NP BT MV AF",
    "east_asia": "CN JP KR KP TW HK MO MN",
    "southeast_asia": "TH VN PH ID MY SG MM KH LA BN TL",
    "oceania": (
        "AU NZ PG FJ NC VU SB WS TO PF GU FM MH MP PW NR KI TV CK NU WF AS PN NF"
    ),
}

COUNTRY_TO_REGION = {}
for _key, _codes in _GROUPS.items():
    for _c in _codes.split():
        assert _c not in COUNTRY_TO_REGION, _c
        COUNTRY_TO_REGION[_c] = REGION_KEYS.index(_key)


def region_of(country_code):
    """Return region index for an ISO-3166 alpha-2 code, or None if unmapped."""
    return COUNTRY_TO_REGION.get(country_code)
