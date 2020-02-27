import pandas as pd
import os
os.environ["IEX_TOKEN"] = ""
os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = ""
os.environ["APCA_API_SECRET_KEY"] = ""

from pipeline_live.engine import LivePipelineEngine
from pipeline_live.data.sources.iex import list_symbols
from pipeline_live.data.alpaca.pricing import USEquityPricing
from pipeline_live.data.polygon.fundamentals import PolygonCompany
from pipeline_live.data.iex.factors import AverageDollarVolume
from zipline.pipeline import Pipeline

eng = LivePipelineEngine(list_symbols)
top5 = AverageDollarVolume(window_length=20).top(5)
pipe = Pipeline({
    'close': USEquityPricing.close.latest,
    'marketcap': PolygonCompany.marketcap.latest,
}, screen=top5)

df = eng.run_pipeline(pipe)
