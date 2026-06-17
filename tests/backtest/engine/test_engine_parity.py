"""Cross-engine trade-count parity test.

The project's central claim: both engines consume identical signals and
therefore produce the same number of trades.  Equity will differ (backtesting.py
fills on next-bar open; vectorbt fills at the close price) — only trade-count
is asserted here.
"""
from signal_trader.backtest.costs import CostModel
from signal_trader.backtest.engine.backtesting_py import BacktestingPyAdapter
from signal_trader.backtest.engine.vectorbt_engine import VectorbtAdapter

_LOOKBACK = 20
_COST_MODEL = CostModel(commission_per_trade=0.001, slippage=0.0005)


def test_trade_count_parity(ohlcv_frame):
    """Both engines must produce the same number of trades for identical signals."""
    bt_result = BacktestingPyAdapter(_COST_MODEL).run(ohlcv_frame, lookback=_LOOKBACK)
    vbt_result = VectorbtAdapter(_COST_MODEL).run(
        ohlcv_frame["Close"], lookback=_LOOKBACK
    )
    assert bt_result.n_trades == vbt_result.n_trades, (
        f"Trade-count mismatch: backtesting.py={bt_result.n_trades}, "
        f"vectorbt={vbt_result.n_trades}"
    )
