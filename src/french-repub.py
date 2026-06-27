#!/usr/bin/env python3
"""
French Republican Calendar -> iCalendar (.ics) generator.

Converts a range of Gregorian dates into French Republican dates and writes
them out as an .ics file (one all-day event per day), using the `icalendar`
library (pip install icalendar).

Conversion method
------------------
- Day 1 of Year I is 22 September 1792 (the autumn equinox in Paris, and the
  date the First Republic was proclaimed).
- Years I-XIV (1792-1805/06): leap ("sextile") years were determined by the
  autumn equinox and fell, historically, on Years III, VII and XI.
- Years XV onward (the calendar was abolished in 1805 with several proposals
  for a fixed continuation): this script uses Romme's rule, i.e. the same 
  structure as the Gregorian leap rule (divisible by 4, except centuries not 
  divisible by 400), as is conventional for genealogical date converters.
- Each Republican year has 12 months of exactly 30 days, followed by 5
  "sans-culottide" complementary days (6 in a leap year). Months and
  complementary days are not interchangeable: a month index of 13 is used
  here to mean "complementary days".

Rural calendar
--------------
Each of the 360 regular days (and each of the 5-6 complementary days) has
its own "rural calendar" name (a plant, animal, or tool), per the Wikipedia
table: https://en.wikipedia.org/wiki/French_Republican_calendar#Rural_calendar


"""

from dataclasses import dataclass
from datetime import date, timedelta, datetime
from functools import lru_cache
from icalendar import Calendar, Event


# 1 Vendemiaire, Year I = the day the calendar's epoch begins.
REPUBLICAN_EPOCH = date(1792, 9, 22)

# French month names (Year I, Vendemiaire .. Fructidor).
MONTH_NAMES_FR = [
    'Vendémiaire', 'Brumaire', 'Frimaire', 'Nivôse', 'Pluviôse', 'Ventôse',
    'Germinal', 'Floréal', 'Prairial', 'Messidor', 'Thermidor', 'Fructidor'
]

# English translations of the month names (displayed on the 1st of each month).
MONTH_NAMES_EN = [
    'Vintage', 'Fog', 'Frost', 'Snow', 'Rain', 'Wind',
    'Sprouting', 'Flowering', 'Meadows', 'Harvest', 'Warmth', 'Fruits'
]

# Rural-calendar day names: 360 regular days (12 months x 30 days) followed
# by 5 sans-culottide days and 1 extra leap-year day ("La Fete de la
# Revolution"), for 366 entries total. Index 0 = 1 Vendemiaire.
RURAL_DAY_NAMES = [
    'Grape', 'Saffron', 'Chestnut', 'Autumn crocus', 'Horse',
    'Impatiens', 'Carrot', 'Amaranth', 'Parsnip', 'Vat',
    'Potato', 'Strawflower', 'Winter squash', 'Mignonette', 'Donkey',
    "Four o'clock flower", 'Pumpkin', 'Buckwheat', 'Sunflower', 'Wine-press',
    'Hemp', 'Peach', 'Turnip', 'Amaryllis', 'Ox',
    'Eggplant', 'Chili pepper', 'Tomato', 'Barley', 'Barrel',
    'Apple', 'Celery', 'Pear', 'Beetroot', 'Goose',
    'Heliotrope', 'Common fig', 'Black salsify', 'Chequer tree', 'Plough',
    'Salsify', 'Water caltrop', 'Jerusalem artichoke', 'Endive', 'Turkey',
    'Skirret', 'Watercress', 'Leadworts', 'Pomegranate', 'Harrow',
    'Baccharis', 'Azarole', 'Madder', 'Orange', 'Pheasant',
    'Pistachio nut', 'Tuberous pea', 'Quince', 'Service tree', 'Roller',
    'Rampion', 'Cattle turnip', 'Chicory', 'Medlar', 'Pig',
    "Lamb's lettuce", 'Cauliflower', 'Honey', 'Juniper', 'Pickaxe',
    'Wax', 'Horseradish', 'Cedar tree', 'Fir', 'Roe deer',
    'Gorse', 'Cypress tree', 'Ivy', 'Savin juniper', 'Grub-hoe',
    'Sugar maple', 'Heather', 'Reed plant', 'Sorrel', 'Cricket',
    'Pine nut', 'Cork', 'Truffle', 'Olive', 'Shovel',
    'Peat', 'Coal', 'Bitumen', 'Sulphur', 'Dog',
    'Lava', 'Topsoil', 'Manure', 'Saltpeter', 'Flail',
    'Granite', 'Clay', 'Slate', 'Sandstone', 'Rabbit',
    'Flint', 'Marl', 'Limestone', 'Marble', 'Winnowing fan',
    'Gypsum', 'Salt', 'Iron', 'Copper', 'Cat',
    'Tin', 'Lead', 'Zinc', 'Mercury', 'Sieve',
    'Spurge-laurel', 'Moss', "Butcher's broom", 'Snowdrop', 'Bull',
    'Laurustinus', 'Tinder polypore', 'Daphne mezereum', 'Poplar', 'Axe',
    'Hellebore', 'Broccoli', 'Bay laurel', 'Filbert', 'Cow',
    'Box tree', 'Lichen', 'Yew tree', 'Lungwort', 'Billhook',
    'Pennycress', 'Rose daphne', 'Couch grass', 'Common knotgrass', 'Hare',
    'Woad', 'Hazel', 'Cyclamen', 'Celandine', 'Sleigh',
    'Coltsfoot', 'Dogwood', 'Matthiola', 'Privet', 'Billygoat',
    'Wild ginger', 'Italian buckthorn', 'Violet', 'Goat willow', 'Spade',
    'Narcissus', 'Elm', 'Common fumitory', 'Hedge mustard', 'Goat',
    'Spinach', 'Doronicum', 'Pimpernel', 'Chervil', "Gardener's line",
    'Mandrake', 'Parsley', 'Scurvy-grass', 'Daisy', 'Tuna',
    'Dandelion', 'Wood anemone', 'Maidenhair fern', 'Ash tree', 'Dibber',
    'Primrose', 'Plane tree', 'Asparagus', 'Tulip', 'Hen',
    'Chard', 'Birch', 'Daffodil', 'Alder', 'Incubator',
    'Periwinkle', 'Hornbeam', 'Morel', 'Beech tree', 'Bee',
    'Lettuce', 'Larch', 'Hemlock', 'Radish', 'Beehive',
    'Judas tree', 'Romaine lettuce', 'Horse chestnut', 'Arugula', 'Pigeon',
    'Lilac', 'Anemone', 'Pansy', 'Bilberry', 'Grafting knife',
    'Rose', 'Oak tree', 'Fern', 'Hawthorn', 'Nightingale',
    'Common columbine', 'Lily of the valley', 'Button mushroom', 'Hyacinth', 'Rake',
    'Rhubarb', 'Sainfoin', 'Wallflower', 'Fan palm tree', 'Silkworm',
    'Comfrey', 'Salad burnet', 'Basket of gold', 'Orache', 'Weeding hoe',
    'Sea thrift', 'Fritillary', 'Borage', 'Valerian', 'Carp',
    'Euonymus', 'Chives', 'Bugloss', 'White mustard', "Shepherd's crook",
    'Lucerne', 'Daylily', 'Clover', 'Angelica', 'Duck',
    'Lemon balm', 'Oat grass', 'Martagon lily', 'Wild thyme', 'Scythe',
    'Strawberry', 'Betony', 'Pea', 'Acacia', 'Quail',
    'Carnation', 'Elderflower', 'Poppy plant', 'Linden', 'Pitchfork',
    'Cornflower', 'Camomile', 'Honeysuckle', 'Bedstraw', 'Tench',
    'Jasmine', 'Vervain', 'Thyme', 'Peony', 'Handcart',
    'Rye', 'Oat', 'Onion', 'Speedwell', 'Mule',
    'Rosemary', 'Cucumber', 'Shallot', 'Wormwood', 'Sickle',
    'Coriander', 'Artichoke', 'Clove', 'Lavender', 'Chamois',
    'Tobacco', 'Redcurrant', 'Hairy vetchling', 'Cherry', 'Livestock pen',
    'Mint', 'Cumin', 'Bean', 'Alkanet', 'Guineafowl',
    'Sage', 'Garlic', 'Tare', 'Wheat', 'Shawm',
    'Spelt', 'Common mullein', 'Melon', 'Ryegrass', 'Ram',
    'Horsetail', 'Mugwort', 'Safflower', 'Blackberry', 'Watering can',
    'Foxtail millet', 'Common glasswort', 'Apricot', 'Basil', 'Ewe',
    'Marshmallow', 'Flax', 'Almond', 'Gentian', 'Lock',
    'Carline thistle', 'Caper', 'Lentil', 'Inula', 'Otter',
    'Myrtle', 'Rapeseed', 'Lupin', 'Cotton', 'Mill',
    'Plum', 'Millet', 'Puffball', 'Six-row barley', 'Salmon',
    'Tuberose', 'Winter barley', 'Apocynum', 'Liquorice', 'Ladder',
    'Watermelon', 'Fennel', 'European barberry', 'Walnut', 'Trout',
    'Lemon', 'Teasel', 'Buckthorn', 'Mexican marigold', 'Harvesting basket',
    'Wild rose', 'Hazelnut', 'Hops', 'Sorghum', 'Crayfish',
    'Bitter orange', 'Goldenrod', 'Maize', 'Sweet chestnut', 'Pack basket',
    'La Fête de la Vertu (virtue)', 'La Fête du Génie (talent)', 'La Fête du Travail (labour)', 
    "La Fête de l'Opinion (convictions)", 'La Fête des Récompenses (honors)',
    'La Fête de la Révolution'
]

assert len(MONTH_NAMES_FR) == 12
assert len(MONTH_NAMES_EN) == 12
assert len(RURAL_DAY_NAMES) == 366


def is_republican_leap_year(rep_year: int) -> bool:
    """Was the given Republican year a 366-day (sextile) year?"""
    if rep_year <= 14:
        return rep_year in (3, 7, 11)
    return rep_year % 4 == 0 and (rep_year % 100 != 0 or rep_year % 400 == 0)


def days_in_republican_year(rep_year: int) -> int:
    """Number of days (365 or 366) in the given Republican year."""
    return 366 if is_republican_leap_year(rep_year) else 365


@lru_cache(maxsize=None)
def republican_year_start(rep_year: int) -> date:
    """Gregorian date of 1 Vendemiaire of the given Republican year."""
    if rep_year < 1:
        raise ValueError("Republican years are counted from 1.")
    if rep_year == 1:
        return REPUBLICAN_EPOCH
    previous_start = republican_year_start(rep_year - 1)
    return previous_start + timedelta(days=days_in_republican_year(rep_year - 1))


def republican_year_for(greg_date: date) -> int:
    """Which Republican year a Gregorian date falls into."""
    if greg_date < REPUBLICAN_EPOCH:
        raise ValueError(f"Date {greg_date} predates the Republican epoch ({REPUBLICAN_EPOCH}).")
    # A Republican year is never shorter than 365 days, so this is a safe
    # (if slightly conservative) starting estimate; we then walk forward.
    rep_year = (greg_date - REPUBLICAN_EPOCH).days // 366 + 1
    while greg_date >= republican_year_start(rep_year + 1):
        rep_year += 1
    return rep_year


def day_of_year_to_month_day(day_of_year: int) -> tuple[int, int]:
    """Convert a 1-indexed day-of-year into (month, day_of_month).

    Months 1-12 have 30 days each (days 1-360). Day-of-year values above
    360 fall in the complementary period, reported as "month 13".
    """
    if day_of_year <= 360:
        month = (day_of_year - 1) // 30 + 1
        day = (day_of_year - 1) % 30 + 1
    else:
        month = 13
        day = day_of_year - 360
    return month, day


@dataclass(frozen=True)
class RepublicanDate:
    year: int           # Republican year (Year I = 1)
    month: int          # 1-12, or 13 for the complementary days
    day: int            # day of month (1-30), or day within the
                         # complementary period (1-5, or 1-6 in a leap year)
    day_of_year: int    # 1-365, or 1-366 in a leap year
    rural_name: str      # rural-calendar name for this day


def gregorian_to_republican(greg_date: date) -> RepublicanDate:
    """Convert a Gregorian `date` into its Republican equivalent."""
    rep_year = republican_year_for(greg_date)
    day_of_year = (greg_date - republican_year_start(rep_year)).days + 1
    month, day = day_of_year_to_month_day(day_of_year)
    rural_name = RURAL_DAY_NAMES[day_of_year - 1]
    return RepublicanDate(rep_year, month, day, day_of_year, rural_name)


def format_republican_date(rep_date: RepublicanDate) -> str:
    """Render a RepublicanDate as e.g. '12 Nivose, Clay' or, for a
    complementary day, 'La Fete de la Revolution'.
    The number of year is appended on 1 Vendemiaire.
    """
    if rep_date.month <= 12:
        _year = f' {rep_date.year}' if rep_date.month == 1 and rep_date.day == 1 else ''
        month_name = MONTH_NAMES_FR[rep_date.month - 1]
        if rep_date.day == 1:
            month_name += f" ({MONTH_NAMES_EN[rep_date.month - 1]})"
        return f"{rep_date.day} {month_name}{_year}, {rep_date.rural_name}"
    return f"{rep_date.rural_name}"


def iter_dates(start: date, end: date):
    """Yield every date from `start` to `end`, inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def build_calendar(start: date, end: date) -> Calendar:
    """Build an `icalendar.Calendar` with one all-day event per day in
    [start, end], named with its Republican-calendar equivalent."""
    if end < start:
        raise ValueError("end date must not be before start date")

    cal = Calendar()
    cal.add("prodid", "-//French Republican Calendar Converter//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "French Republican")

    for day in iter_dates(start, end):
        rep_date = gregorian_to_republican(day)
        event = Event()
        event.add("summary", format_republican_date(rep_date))
        event.add("dtstart", day)
        event.add("dtend", day + timedelta(days=1))
        event.add("dtstamp", datetime.now())
        event.add("uid", f"{day.isoformat()}@french-republican.local")
        cal.add_component(event)

    return cal


def write_ics(start: date, end: date, output_file: str) -> str:
    """Build the calendar and write it to `output_file`. Returns the path."""
    if not output_file.endswith(".ics"):
        output_file += ".ics"
    calendar = build_calendar(start, end)
    with open(output_file, "wb") as f:
        f.write(calendar.to_ical())
    return output_file


def main() -> None:
    start = date(2024, 1, 1)
    end = date(2033, 12, 31)
    output_file = f"../ics/french-republican-{start.year}-{end.year}.ics"

    path = write_ics(start, end, output_file)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
