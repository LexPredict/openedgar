"""
MIT License

Copyright (c) 2018 ContraxSuite, LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# Client imports
import datetime

from nose.tools import assert_list_equal, assert_equal, assert_is_instance

import openedgar.clients.edgar
import openedgar.clients.s3


def test_client_list_dir_index():
    """
    Test listing directory with client method.
    :return:
    """
    # Fetch list
    result = openedgar.clients.edgar.list_path("/Archives/edgar/daily-index/1994/")

    # Compare lists
    expected = ['/Archives/edgar/daily-index/1994//QTR3/',
                '/Archives/edgar/daily-index/1994//QTR4/']
    assert_list_equal(result, expected)


def test_client_list_dir_filing():
    """
    Test listing directory with client method.
    :return:
    """
    # Fetch list
    result = len(openedgar.clients.edgar.list_path("/Archives/edgar/data/1297937/000107878205000139/"))

    # Compare length
    expected = 13
    assert_equal(result, expected)


def test_client_get_buffer():
    """
    Test retrieving a buffer over HTTP.
    :return:
    """
    uri = "/Archives/edgar/data/1297937/000107878205000139/0001078782-05-000139.txt"
    buffer, last_modified_date = openedgar.clients.edgar.get_buffer(uri)
    result = len(buffer)
    expected = 1632839
    assert_equal(result, expected)
    assert_is_instance(last_modified_date, datetime.date)


def test_client_index_year():
    """
    Test retrieving list of indices for a given year.
    """
    index_list = openedgar.clients.edgar.list_index_by_year(1994)
    result = len(index_list)
    expected = 119
    assert_equal(result, expected)
