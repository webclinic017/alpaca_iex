import pandas as pd



#import quantopian.algorithm as algo
import pylivetrader.algorithm as algo

#import quantopian.optimize as opt  # !!!!
#import zipline.optimize as opt # ?????

import os
os.environ["IEX_TOKEN"] = "pk_7de7b2552dac4e3b805bfc0558a7e3ee"


from zipline.pipeline import Pipeline
from pipeline_live.data.alpaca.factors import SimpleBeta, RSI, AnnualizedVolatility
from pipeline_live.data.iex.classifiers import Sector

#from quantopian.pipeline.filters import QTradableStocksUS
from pipeline_live.data.iex.pricing import USEquityPricing as QTradableStocksUS



# Algorithm Parameters

# --------------------

UNIVERSE_SIZE = 1000

LIQUIDITY_LOOKBACK_LENGTH = 100



MINUTES_AFTER_OPEN_TO_TRADE = 5



MAX_GROSS_LEVERAGE = 1.0

MAX_SHORT_POSITION_SIZE = 0.05  # 5%

MAX_LONG_POSITION_SIZE = 0.05   # 5%



ORDER_IMAL = True # True for order_optimal_portfolio, False for calculate_optimal_portfolio



MAXIMIZE_ALPHA = True # True for MaximizeAlpha, False for TargetWeights





def initialize(context):

    # Universe Selection

    # ------------------

    # universe = QTradableStocksUS()

    

    QTU = QTradableStocksUS()

    

    universe = (

        AnnualizedVolatility(mask=QTU)

        .percentile_between(80,100))



    # From what remains, each month, take the top UNIVERSE_SIZE stocks by average dollar

    # volume traded.

    # monthly_top_volume = (

    #     AverageDollarVolume(window_length=LIQUIDITY_LOOKBACK_LENGTH)

    #     .top(UNIVERSE_SIZE, mask=base_universe)

    #     .downsample('week_start')

    # )

    # The final universe is the monthly top volume &-ed with the original base universe.

    # &-ing these is necessary because the top volume universe is calculated at the start 

    # of each month, and an asset might fall out of the base universe during that month.

    # universe = monthly_top_volume & base_universe



    # Alpha Generation

    # ----------------

    # Compute Z-scores of free cash flow yield and earnings yield. 

    # Both of these are fundamental value measures.

    # fcf_zscore = Fundamentals.fcf_yield.latest.zscore(mask=universe)

    # yield_zscore = Fundamentals.earning_yield.latest.zscore(mask=universe)

    # sentiment_zscore = psychsignal.stocktwits.bull_minus_bear.latest.zscore(mask=universe)

    rsi_zscore = -RSI(mask=universe).zscore(mask=universe)

    

    # Alpha Combination

    # -----------------

    # Assign every asset a combined rank and center the values at 0.

    # For UNIVERSE_SIZE=500, the range of values should be roughly -250 to 250.

    combined_alpha = rsi_zscore.rank().demean()

    

    # beta = 0.66*RollingLinearRegressionOfReturns(

    #                 target=sid(8554),

    #                 returns_length=5,

    #                 regression_length=260,

    #                 mask=combined_alpha.notnull() & Sector().notnull()

    #                 ).beta + 0.33*1.0

    

    beta = SimpleBeta(target=sid(8554),

                      regression_length=260,

                      allowed_missing_percentage=1.0

                     )

    

    # Schedule Tasks

    # --------------

    # Create and register a pipeline computing our combined alpha and a sector

    # code for every stock in our universe. We'll use these values in our 

    # optimization below.

    pipe_1 = Pipeline(

        columns={

            'alpha': combined_alpha,

            'sector': Sector(),

            'beta': beta,

        },

        # combined_alpha will be NaN for all stocks not in our universe,

        # but we also want to make sure that we have a sector code for everything

        # we trade.

        screen=combined_alpha.notnull() & Sector().notnull() & beta.notnull(),

    )

    algo.attach_pipeline(pipe_1, 'pipe')

    

    pipe_2 = Pipeline(

        columns={

        'beta': beta,

        },

        screen=QTU,

    )

    algo.attach_pipeline(pipe_2, 'QTU')



    # Schedule a function, 'do_portfolio_construction', to run twice a week

    # ten minutes after market open.

    # algo.schedule_function(

    #     do_portfolio_construction,

    #     date_rule=algo.date_rules.week_start(),

    #     time_rule=algo.time_rules.market_open(minutes=MINUTES_AFTER_OPEN_TO_TRADE),

    #     half_days=False,

    # )

    

    algo.schedule_function(

        do_portfolio_construction,

        date_rule=algo.date_rules.every_day(),

        time_rule=algo.time_rules.market_open(minutes=MINUTES_AFTER_OPEN_TO_TRADE),

        half_days=False,

    )

    

    # record my portfolio variables at the end of day

    algo.schedule_function(func=recording_statements,

                      date_rule=date_rules.every_day(),

                      time_rule=time_rules.market_close(),

                      half_days=True)

    

    set_commission(commission.PerShare(cost=0, min_trade_cost=0))

    set_slippage(slippage.FixedSlippage(spread=0))



def before_trading_start(context, data):

    # Call pipeline_output in before_trading_start so that pipeline

    # computations happen in the 5 minute timeout of BTS instead of the 1

    # minute timeout of handle_data/scheduled functions.

    context.pipeline_data = algo.pipeline_output('pipe')

    context.QTU = algo.pipeline_output('QTU')



def recording_statements(context, data):

    

    num_positions = len(context.portfolio.positions)



    record(num_positions=num_positions)

    record(leverage=context.account.leverage)

    

    n_QTU = 0

    for stock in list(context.portfolio.positions.keys()):

        if stock in list(context.QTU['beta'].keys()):

            n_QTU += 1

    

    if num_positions > 0:

        pct_QTU = n_QTU/num_positions

    else:

        pct_QTU = 0

    

    record(pct_QTU = pct_QTU)

    

# Portfolio Construction

# ----------------------

def do_portfolio_construction(context, data):

    pipeline_data = context.pipeline_data



    # Objective

    # ---------

    # For our objective, we simply use our naive ranks as an alpha coefficient

    # and try to maximize that alpha.

    # 

    # This is a **very** naive model. Since our alphas are so widely spread out,

    # we should expect to always allocate the maximum amount of long/short

    # capital to assets with high/low ranks.

    #

    # A more sophisticated model would apply some re-scaling here to try to generate

    # more meaningful predictions of future returns.

    if MAXIMIZE_ALPHA:

        objective = opt.MaximizeAlpha(pipeline_data.alpha)

    else:

        objective = opt.TargetWeights(pipeline_data.alpha)



    # Constraints

    # -----------

    # Constrain our gross leverage to 1.0 or less. This means that the absolute

    # value of our long and short positions should not exceed the value of our

    # portfolio.

    constrain_gross_leverage = opt.MaxGrossExposure(MAX_GROSS_LEVERAGE)

    

    # Constrain individual position size to no more than a fixed percentage 

    # of our portfolio. Because our alphas are so widely distributed, we 

    # should expect to end up hitting this max for every stock in our universe.

    constrain_pos_size = opt.PositionConcentration.with_equal_bounds(

        -MAX_SHORT_POSITION_SIZE,

        MAX_LONG_POSITION_SIZE,

    )



    # Constrain ourselves to allocate the same amount of capital to 

    # long and short positions.

    market_neutral = opt.DollarNeutral()



    # Run the optimization. This will calculate new portfolio weights and

    # manage moving our portfolio toward the target.

    

    if ORDER_OPTIMAL:

        

        algo.order_optimal_portfolio(

            objective=objective,

            constraints=[

            constrain_gross_leverage,

            constrain_pos_size,

            market_neutral,

            ],

        )

    

    else:

        

        weights = opt.calculate_optimal_portfolio(  

            objective=objective,  

            constraints=[

            constrain_gross_leverage,

            constrain_pos_size,

            market_neutral,

            ],  

        )

    

        objective = opt.TargetWeights(weights)

    

        order_optimal_portfolio(  

            objective=objective,  

            constraints=[],  

            )
