import json
import io

import requests
import pandas as pd
from datetime import datetime, timedelta

from typing import Union


def _format_usgs_lake_names(name):
    return name.split()[1].lower()


def scrape(start: Union[datetime, None]=None,
           end: Union[datetime, None]=None) -> pd.DataFrame:
    """
    Scrape Madison lake heights from public USGS data.
    Heights reported are the gage height + datum elevation.

    Inputs
    ------
    start : datetime | None
        Starting timestamp to collect data from. If `None`
        then `end` must also be `None`, and in this case just the most
        recent sample is returned.
    end : datetime | None
        End timestamp to collect data to. If `None` then go to
        the most recently reported data.

    Returns
    -------
    df : pandas.DataFrame
        A pandas dataframe of lake heights. Each lake has a column.
    """
    date_format = '%Y-%m-%d'
    if start is None:
        start_arg = ''
    else:
        start_arg = '&startDT={}'.format(start.strftime(date_format))

    if end is None:
        end_arg = ''
    elif start is None:
        raise ValueError('If start is None, then end must be None too.')
    else:
        end_arg = '&endDT={}'.format(end.strftime(date_format))

    # See https://waterdata.usgs.gov/wi/nwis/current/?type=dane&group_key=NONE
    lake_name_to_usgs_site_num = {
        'MENDOTA': '05428000',
        'MONONA': '05429000',
        'WAUBESA': '05429485',
        'KEGONSA': '425715089164700'
    }
    sites = ','.join(lake_name_to_usgs_site_num.values())

    base_url = 'http://waterservices.usgs.gov/nwis/iv/?'
    url_args = f'&sites={sites}&format=json{start_arg}{end_arg}'

    r = requests.post(base_url + url_args)
    d = json.loads(r.text)
    df = pd.DataFrame({})
    for ts in d['value']['timeSeries']:
        lake_name = _format_usgs_lake_names(ts['sourceInfo']['siteName'])
        values = ts['values'][0]['value']
        gage_heights = [float(v['value']) for v in values]
        times = [v['dateTime'] for v in values]
        assert len(times) == len(gage_heights)
        df[lake_name] = pd.Series(dict(zip(times, gage_heights)))

    base_datum_url = 'https://waterservices.usgs.gov/nwis/site/?'
    datum_url_args = f'&sites={sites}&format=rdb'
    r = requests.post(base_datum_url + datum_url_args)
    no_hash = '\n'.join(l for l in r.text.split('\n') if not l.startswith('#'))
    datum = pd.read_csv(
        io.StringIO(no_hash),
        delimiter='\t'
    )
    # first row is not useful info
    datum = datum.iloc[1:]
    datum['station_nm'] = datum['station_nm'].apply(_format_usgs_lake_names)
    datum.set_index('station_nm', drop=True, inplace=True)
    datum['alt_va'] = datum['alt_va'].apply(float)
    for name, datum_elevation in datum['alt_va'].iteritems():
        df[name] += datum_elevation

    df.index = pd.to_datetime(df.index, utc=True)

    return df
