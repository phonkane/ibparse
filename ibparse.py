#!/usr/bin/env python
# -*- coding: UTF-8

import sys
import csv
import getopt
import xml.etree.ElementTree as ET
import urllib2
from datetime import datetime, timedelta


ecb_base_url='https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/'

positions = {}
exchange_rates = {}
contracts = {}


def date_sort(elem):
    return elem[6]


def download_currency_xml(filename):
    u = urllib2.urlopen(ecb_base_url + filename)
    f = open(filename, 'wb')
    buf = u.read()
    if buf:
        f.write(buf)


def add_to_exchange_rates(currency, download_xml):
    filename = currency.lower() + '.xml'
    if download_xml:
        download_currency_xml(filename)
    try:
        f = open(filename, 'rb')
    except IOError:
        download_currency_xml(filename)
        f = open(filename, 'rb')
    xml = f.read()
    tree = ET.parse(filename)
    root = tree.getroot()
    rate_data = {}
    for child in root:
        if 'DataSet' in str(child.tag):
            for grandchild in child:
                if 'Series' in str(grandchild.tag):
                    for entry in grandchild:
                        for item in entry.items():
                            if item[0] == 'TIME_PERIOD':
                                key = item[1]
                            if item[0] == 'OBS_VALUE':
                                rate = float(item[1])
                        rate_data[key] = rate
    exchange_rates[currency] = rate_data


def find_exchange_rate(currency, date):
    if currency != 'EUR':
        rate_data = exchange_rates[currency]
        while date not in rate_data:
            # trade was done on a day without ECB reference rate; try previous
            date = datetime.strftime(datetime.strptime(date, '%Y-%m-%d') - timedelta(1), '%Y-%m-%d')
        exchange_rate = rate_data[date]
    else:
        exchange_rate = 1.0
    return exchange_rate


def fi_style_date(date):
    return datetime.strftime(datetime.strptime(date, '%Y-%m-%d'), '%d.%m.%Y')


def process_stocks(line, year, download_xml):
    # field  content      example
    # 4      currency     'USD'
    # 5      ticker       'GILD'
    # 6      date         '2018-06-18, 20:34:11'
    # 7      amount       10
    # 8      price        69.45
    # 10     total price  -695.5
    # 11     commission   -0.33125725
    # 12     total cash   694.83125725
    #print(line)
    ticker = line[5]
    conid = contracts[ticker][1]
    desc = contracts[ticker][0]
    amount = int(str(line[7]).replace(',', ''))
    price = float(line[8])
    commission = -float(line[11])
    currency = line[4]
    date = line[6][:10]
    if currency != 'EUR' and currency not in exchange_rates:
        add_to_exchange_rates(currency, download_xml)
    exchange_rate = find_exchange_rate(currency, date)
#    print('%s: %s %d %s (conid %s) @%f comm %f %s %f' %(date, 'buy' if amount > 0 else 'sell', abs(amount), ticker, conid, price, commission, currency, exchange_rate))
    if conid not in positions:
        positions[conid] = []
    if amount > 0: # buy trade
        positions[conid].append((amount, price / exchange_rate, commission / exchange_rate, date))
    if amount < 0: # sell trade
        left = -amount
        while left:
            lotsize = left
            position = positions[conid]
            if len(position) > 0:
                head = position[0]
                if lotsize >= head[0]:
#                    print('sell entire head!')
                    lotsize = head[0]
                    position.pop(0)
                else:
                    position[0] = (head[0] - lotsize, head[1], head[2], head[3])

                if year and year != date[:4]: # gah, parse date!
                    left -= lotsize
                    continue

                profit = lotsize * (price / exchange_rate - head[1])
#                print('%s: sold %d %s @%f %s: %f EUR paid %f EUR profit %f EUR comm %f' % (date, lotsize, desc, price, currency, lotsize * price / exchange_rate, lotsize * head[1], profit, commission))
                buy_expense = head[2] * lotsize / head[0]
                sell_expense = commission / exchange_rate * lotsize / -amount
                profit -= buy_expense
                profit -= sell_expense
                print('-----------------------------------------')
                print('Arvopaperin nimi:  %s' %(desc))
                print('Lukumäärä:         %d' %(lotsize))
                print('Luovutusaika:      %s' %(fi_style_date(date)))
                print('Luovutushinta:     %.2f' %(lotsize * price / exchange_rate))
                print('Hankinta-aika:     %s' %(fi_style_date(head[3])))
                print('Hankintahinta:     %.2f' %(lotsize * head[1]))
                print('Hankintakulut:     %.2f' %(buy_expense))
                print('Myyntikulut:       %.2f' %(sell_expense))
                print('%s:            %.2f' %('Voitto' if profit >= 0.0 else 'Tappio', profit))
            else:
                print('cannot handle short positions: %s' % (desc))
            left -= lotsize


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dy:')
    except getopt.GetoptError as err:
        print('%s' %(str(err)))
        sys.exit(1)

    year = None
    download = False
    for opt, arg in opts:
        if opt == '-d':
            download = True
        if opt == '-y':
            year = arg

    reader = csv.reader(sys.stdin)
    events = []
    for line in reader:
        if line[0] == 'Trades' and line[1] == 'Data' and line[2] == 'Order' and line[3][:6] == 'Stocks':
            events.append(line)
        if line[0] == 'Financial Instrument Information' and line[1] == 'Data' and line[2] == 'Stocks':
            for ticker in line[3].split(', '):
                contracts[ticker] = (line[4], line[5])
    events.sort(key=date_sort)
    for line in events:
        process_stocks(line, year, download)


if __name__ == '__main__':
    main()
