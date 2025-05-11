# backtester.py
import pandas as pd
from datamodel import TradingState, OrderDepth, Listing, Trade
from trader import Trader
from typing import Dict, List
import numpy as np


class Backtester:
    def __init__(self, data_path):
        # Read CSV with semicolon delimiter
        self.data = pd.read_csv(data_path, delimiter=';')

        # Validate required columns
        required_columns = [
            'timestamp', 'product',
            'bid_price_1', 'bid_volume_1',
            'ask_price_1', 'ask_volume_1',
            'mid_price'
        ]
        self._validate_columns(required_columns)

        self.trader = Trader()
        self.results = []
        self.current_positions = {'RAINFOREST_RESIN': 0, 'KELP': 0}
        self.pnl = 0
        self.trade_history = []

    def _validate_columns(self, required_cols):
        missing = [col for col in required_cols if col not in self.data.columns]
        if missing:
            raise ValueError(
                f"CSV missing required columns: {', '.join(missing)}")

    def run_backtest(self):
        grouped = self.data.groupby('timestamp')

        for timestamp, group in grouped:
            # Initialize market data collection
            market_data = {
                'timestamp': timestamp,
                'pnl': self.pnl,
                'total_volume': 0
            }

            # 1. Create Listings and Order Depths
            listings = {}
            order_depths = {}

            for _, row in group.iterrows():
                product = row['product']

                # Build OrderDepth from all available levels
                order_depth = OrderDepth()

                # Process bids (levels 1-3)
                for i in [1, 2, 3]:
                    bid_price = row.get(f'bid_price_{i}')
                    bid_vol = row.get(f'bid_volume_{i}')
                    if pd.notna(bid_price) and pd.notna(bid_vol):
                        order_depth.buy_orders[int(bid_price)] = int(bid_vol)

                # Process asks (levels 1-3)
                for i in [1, 2, 3]:
                    ask_price = row.get(f'ask_price_{i}')
                    ask_vol = row.get(f'ask_volume_{i}')
                    if pd.notna(ask_price) and pd.notna(ask_vol):
                        order_depth.sell_orders[int(ask_price)] = int(ask_vol)

                order_depths[product] = order_depth
                listings[product] = Listing(
                    symbol=product,
                    product=product,
                    denomination=product
                )

                # Store market data
                market_data[f'{product}_mid'] = row['mid_price']
                market_data[f'{product}_best_bid'] = max(
                    order_depth.buy_orders.keys(), default=np.nan)
                market_data[f'{product}_best_ask'] = min(
                    order_depth.sell_orders.keys(), default=np.nan)

            # 2. Create TradingState
            state = TradingState(
                timestamp=int(timestamp),
                listings=listings,
                order_depths=order_depths,
                own_trades={'RAINFOREST_RESIN': [], 'KELP': []},
                market_trades={'RAINFOREST_RESIN': [], 'KELP': []},
                position=self.current_positions.copy(),
                observations={}
            )

            # 3. Execute trading strategy
            result = self.trader.run(state)[0]

            # 4. Process orders with historical execution
            for product in result:
                for order in result[product]:
                    self._process_order(
                        product=product,
                        order=order,
                        order_depth=order_depths[product],
                        timestamp=timestamp
                    )

            # 5. Update results
            market_data.update({
                'RAINFOREST_RESIN_position': self.current_positions['RAINFOREST_RESIN'],
                'KELP_position': self.current_positions['KELP'],
                'total_volume': sum(t['quantity'] for t in self.trade_history[-10:])
            })
            self.results.append(market_data)

        return pd.DataFrame(self.results)

    def _process_order(self, product, order, order_depth, timestamp):
        """Execute orders against historical order book"""
        if order.quantity > 0:  # Buy order
            best_ask = min(order_depth.sell_orders.keys())
            if order.price >= best_ask:
                fill_qty = min(
                    order.quantity, order_depth.sell_orders[best_ask])
                self._record_trade(product, best_ask,
                                   fill_qty, 'buy', timestamp)
        else:  # Sell order
            best_bid = max(order_depth.buy_orders.keys())
            if order.price <= best_bid:
                fill_qty = min(abs(order.quantity),
                               order_depth.buy_orders[best_bid])
                self._record_trade(product, best_bid,
                                   fill_qty, 'sell', timestamp)

    def _record_trade(self, product, price, quantity, side, timestamp):
        """Update positions and PnL"""
        self.current_positions[product] += quantity if side == 'buy' else -quantity
        self.pnl += quantity * (price * (-1 if side == 'buy' else 1))
        self.trade_history.append({
            'timestamp': timestamp,
            'product': product,
            'price': price,
            'quantity': quantity,
            'side': side
        })
