#!/usr/bin/env python
import os
os.environ["IEX_TOKEN"] = ""
os.environ["APCA_API_KEY_ID"] = ""
os.environ["APCA_API_SECRET_KEY"] = ""


from pipeline_live.engine import LivePipelineEngine
from pipeline_live.data.iex.pricing import USEquityPricing
from pipeline_live.data.iex.classifiers import Sector
from pipeline_live.data.iex.factors import AverageDollarVolume
from zipline.pipeline import Pipeline

from pipeline_live.data.sources import alpaca, iex, polygon

from .datamock import mock_iex, mock_tradeapi


def test_alpaca(alpaca_tradeapi, data_path):
    mock_tradeapi.list_assets(alpaca_tradeapi)
    mock_tradeapi.get_barset(alpaca_tradeapi)

    data = alpaca.get_stockprices(2)
    assert data['AA'].iloc[0].close == 172.18


def test_polygon(tradeapi, data_path):
    mock_tradeapi.list_assets(tradeapi)
    mock_tradeapi.list_financials(tradeapi)

    data = polygon.financials()
    assert len(data['AA']) == 5
    assert data['AA'][-1]['totalCash'] > 10e7

    mock_tradeapi.list_companies(tradeapi)
    data = polygon.company()
    assert len(data) == 2
    assert data['AA']['name'] == 'Alcoa Corp'


def test_iex(refdata, stocks, data_path):
    mock_iex.get_available_symbols(refdata)
    mock_iex.get_key_stats(stocks)

    kstats = iex.key_stats()

    assert len(kstats) == 2
    assert kstats['AA']['latestEPSDate'] == '2017-12-30'

    # cached
    kstats = iex.key_stats()
    assert kstats['AA']['returnOnCapital'] is None

    mock_iex.get_financials(stocks)

    financials = iex.financials()
    assert len(financials) == 1
    assert len(financials['AA']) == 4

    ed = iex._ensure_dict(1, ['AA'])
    assert ed['AA'] == 1

    mock_iex.get_chart(stocks)

    data = iex.get_stockprices()
    assert len(data) == 1
    data['AA'].open[1] == 43.2