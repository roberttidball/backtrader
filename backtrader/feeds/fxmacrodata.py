#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2023 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from datetime import date, datetime
import io
import json

from ..utils.py3 import (urlopen, urlquote, ProxyHandler, build_opener,
                         install_opener)

from .. import feed
from ..utils import date2num


__all__ = ['FXMacroDataCSV', 'FXMacroData']


class FXMacroDataCSV(feed.CSVDataBase):
    '''
    Parses pre-downloaded FXMacroData CSV rows.

    The online :class:`FXMacroData` feed converts FXMacroData REST JSON rows
    into ``date,open,high,low,close,volume`` lines.  FXMacroData spot history
    provides one daily value, so open/high/low/close are set to the same value
    and volume is set to zero.
    '''

    _online = False

    def _loadline(self, linetokens):
        dttxt = linetokens[0]  # YYYY-MM-DD
        dt = date(int(dttxt[0:4]), int(dttxt[5:7]), int(dttxt[8:10]))
        dtnum = date2num(datetime.combine(dt, self.p.sessionend))

        self.lines.datetime[0] = dtnum
        self.lines.open[0] = float(linetokens[1])
        self.lines.high[0] = float(linetokens[2])
        self.lines.low[0] = float(linetokens[3])
        self.lines.close[0] = float(linetokens[4])
        self.lines.volume[0] = float(linetokens[5])
        self.lines.openinterest[0] = 0.0

        return True


class FXMacroData(FXMacroDataCSV):
    '''
    Downloads daily FX spot rates from FXMacroData.

    Specific parameters:

      - ``dataname``: FX pair to download, for example ``EURUSD`` or
        ``EUR/USD``.

      - ``baseurl``: FXMacroData API base URL.

      - ``apikey``: optional FXMacroData Professional API key.  It is sent as
        the REST ``api_key`` query parameter.

      - ``proxies``: optional proxy dictionary as in ``{'http':
        'http://myproxy.com'}``.

      - ``buffered``: retained for consistency with other online feeds.  The
        JSON response is parsed before the CSV parser is started.
    '''

    _online = True

    params = (
        ('baseurl', 'https://fxmacrodata.com/api/v1'),
        ('proxies', {}),
        ('buffered', True),
        ('apikey', None),
    )

    def start(self):
        self.error = None

        base, quote = self._split_pair(self.p.dataname)
        url = '{}/forex/{}/{}'.format(
            self.p.baseurl.rstrip('/'), base.lower(), quote.lower())

        urlargs = []

        if self.p.fromdate:
            urlargs.append('start_date={}'.format(
                self.p.fromdate.strftime('%Y-%m-%d')))

        if self.p.todate:
            urlargs.append('end_date={}'.format(
                self.p.todate.strftime('%Y-%m-%d')))

        if self.p.apikey is not None:
            urlargs.append('api_key={}'.format(urlquote(self.p.apikey)))

        if urlargs:
            url += '?' + '&'.join(urlargs)

        if self.p.proxies:
            proxy = ProxyHandler(self.p.proxies)
            opener = build_opener(proxy)
            install_opener(opener)

        try:
            datafile = urlopen(url)
            payload = json.loads(datafile.read().decode('utf-8'))
            datafile.close()
        except IOError as e:
            self.error = str(e)
            return

        rows = payload.get('data', [])
        if not rows:
            self.error = 'No FXMacroData rows returned for {}'.format(
                self.p.dataname)
            return

        lines = []
        for row in rows:
            value = row.get('val')
            if value is None:
                continue
            lines.append('{},{},{},{},{},0.0\n'.format(
                row['date'], value, value, value, value))

        self.f = io.StringIO(''.join(lines), newline=None)
        super(FXMacroData, self).start()

    @staticmethod
    def _split_pair(pair):
        clean_pair = pair.replace('/', '').replace('-', '').upper()

        if len(clean_pair) != 6:
            raise ValueError(
                'FXMacroData dataname should be a six-letter FX pair, '
                'for example EURUSD')

        return clean_pair[:3], clean_pair[3:]
