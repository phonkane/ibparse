import pytest
import ibparse

def test_fi_date_happy():
    date = '2018-11-03'
    fidate = ibparse.fi_style_date(date)
    assert fidate == '03.11.2018'
