import json
import numpy as np
import pandas as pd
import jsonpickle
from typing import Dict, List, Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

# this is good in profit


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: Dict[Symbol, List[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(
                        state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> List[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: Dict[Symbol, Listing]) -> List[List[Any]]:
        return [[listing.symbol, listing.product, listing.denomination] for listing in listings.values()]

    def compress_order_depths(self, order_depths: Dict[Symbol, OrderDepth]) -> Dict[Symbol, List[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}

    def compress_trades(self, trades: Dict[Symbol, List[Trade]]) -> List[List[Any]]:
        return [[trade.symbol, trade.price, trade.quantity, trade.buyer, trade.seller, trade.timestamp]
                for arr in trades.values() for trade in arr]

    def compress_observations(self, observations: Observation) -> List[Any]:
        return [observations.plainValueObservations, {
            product: [
                obs.bidPrice,
                obs.askPrice,
                obs.transportFees,
                obs.exportTariff,
                obs.importTariff,
                obs.sugarPrice,
                obs.sunlightIndex,
            ] for product, obs in observations.conversionObservations.items()
        }]

    def compress_orders(self, orders: Dict[Symbol, List[Order]]) -> List[List[Any]]:
        return [[order.symbol, order.price, order.quantity] for arr in orders.values() for order in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value[:max_length-3] + "..." if len(value) > max_length else value


logger = Logger()


class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    SQUID_INK = "SQUID_INK"


class StrategyParams:
    RESIN = {
        "fair_value": 10000,
        "take_width": 2,
        "spread": 2,
        "position_limit": 50
    }

    KELP = {
        "take_width": 1.2,        # Reduced from 2 for better liquidity capture
        "min_edge": 1.0,          # Tightened from 1.5 for improved fill rate
        "reversion_beta": -0.45,  # Increased mean reversion strength from -0.35
        "window_size": 6,         # Extended from 3 for smoother signals
        "position_limit": 50,
        "max_order_size": 30       # Added dynamic sizing
    }

    SQUID = {
        "pair_symbol": "KELP",  # Use string instead of Product reference
        "hedge_ratio": 1.0,
        "volatility_window": 20,
        "stop_loss": 2.1,
        "position_limit": 50
    }


class Trader:
    def __init__(self):
        self.position_limits = {
            Product.RAINFOREST_RESIN: 50,
            Product.KELP: 50,
            Product.SQUID_INK: 50
        }
        self.historical_data = {
            Product.KELP: {'timestamps': [], 'mid_prices': []},
            Product.SQUID_INK: {'timestamps': [], 'spreads': []}
        }

    def run(self, state: TradingState):
        result = {}
        trader_data = {}  # Initialize trader_data
        try:
            # Load historical data from state
            if state.traderData:
                trader_data = jsonpickle.decode(state.traderData)

            # Rainforest Resin Strategy
            if Product.RAINFOREST_RESIN in state.order_depths:
                result[Product.RAINFOREST_RESIN] = self.trade_resin(state)

            # Kelp Strategy
            if Product.KELP in state.order_depths:
                result[Product.KELP] = self.trade_kelp(state, trader_data)

            # Squid Ink Strategy
            if Product.SQUID_INK in state.order_depths:
                result[Product.SQUID_INK] = self.trade_squid(state)

            # Update trader_data with latest historical data
            trader_data['historical_data'] = self.historical_data

        except Exception as e:
            logger.print(f"Error: {str(e)}")

        logger.flush(state, result, 0, jsonpickle.encode(trader_data))
        return result, 0, jsonpickle.encode(trader_data)

    def trade_resin(self, state: TradingState) -> List[Order]:
        params = StrategyParams.RESIN
        product = Product.RAINFOREST_RESIN
        position = state.position.get(product, 0)
        orders = []
        order_depth = state.order_depths[product]

        # Get best bids/asks safely
        bids = order_depth.buy_orders.keys()
        asks = order_depth.sell_orders.keys()
        best_bid = max(bids) if bids else params["fair_value"] - 2
        best_ask = min(asks) if asks else params["fair_value"] + 2

        for i in range(3):
            bid_price = params["fair_value"] - params["take_width"] - i
            ask_price = params["fair_value"] + params["take_width"] + i

            if bid_price > best_bid and position < params["position_limit"]:
                quantity = min(10, params["position_limit"] - position)
                orders.append(Order(product, bid_price, quantity))

            if ask_price < best_ask and position > -params["position_limit"]:
                quantity = min(10, params["position_limit"] + position)
                orders.append(Order(product, ask_price, -quantity))

        return orders

    def trade_kelp(self, state: TradingState, trader_data: dict) -> List[Order]:
        params = StrategyParams.KELP
        product = Product.KELP
        position = state.position.get(product, 0)
        orders = []
        order_depth = state.order_depths[product]

        # Safe price calculation
        bids = order_depth.buy_orders.keys()
        asks = order_depth.sell_orders.keys()
        if not bids or not asks:
            return orders

        best_ask = min(asks)
        best_bid = max(bids)
        mid_price = (best_ask + best_bid) / 2

        # Update history
        hist = self.historical_data[product]
        hist['timestamps'].append(state.timestamp)
        hist['mid_prices'].append(mid_price)

        # Maintain window size
        if len(hist['mid_prices']) > params["window_size"]:
            hist['mid_prices'].pop(0)
            hist['timestamps'].pop(0)

        # Generate orders
        if len(hist['mid_prices']) >= 2:
            last_price = hist['mid_prices'][-2]
            returns = (mid_price - last_price) / last_price
            pred_returns = returns * params["reversion_beta"]
            fair_price = mid_price + (mid_price * pred_returns)

            spread = params["min_edge"]
            orders.append(Order(product, int(fair_price - spread), 5))
            orders.append(Order(product, int(fair_price + spread), -5))

        return orders

    def trade_squid(self, state: TradingState) -> List[Order]:
        params = StrategyParams.SQUID
        product = Product.SQUID_INK
        position = state.position.get(product, 0)
        orders = []

        # Get pair data safely
        pair_symbol = params["pair_symbol"]
        pair_depth = state.order_depths.get(pair_symbol, OrderDepth())

        # Get squid bid
        squid_bids = state.order_depths[product].buy_orders.keys()
        squid_bid = max(squid_bids) if squid_bids else 0

        # Get pair ask
        pair_asks = pair_depth.sell_orders.keys()
        pair_ask = min(pair_asks) if pair_asks else 0

        # Calculate spread
        if squid_bid == 0 or pair_ask == 0:
            return orders

        spread = squid_bid - params["hedge_ratio"] * pair_ask

        # Update historical spread
        hist = self.historical_data[product]
        hist['timestamps'].append(state.timestamp)
        hist['spreads'].append(spread)

        # Maintain volatility window
        spreads = hist['spreads'][-params["volatility_window"]:]
        if len(spreads) < 2:
            return orders

        spread_mean = np.mean(spreads)
        spread_std = np.std(spreads)

        if spread_std == 0:
            return orders

        # Calculate z-score
        spread_z = (spread - spread_mean) / spread_std

        # Generate orders
        max_size = min(params["position_limit"] - abs(position), 10)
        if spread_z > params["stop_loss"]:
            orders.append(Order(product, squid_bid - 1, -max_size))
        elif spread_z < -params["stop_loss"]:
            orders.append(Order(product, squid_bid + 1, max_size))

        return orders
