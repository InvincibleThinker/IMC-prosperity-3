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
        "window_size": 20,          # Historical lookback period
        "volatility_window": 10,    # For ATR calculation
        "risk_multiplier": 0.2,     # Position sizing based on volatility
        "max_position": 50,         # Absolute position limit
        "base_spread": 1.5,         # Minimum spread in normal conditions
        "stop_loss_pct": 0.5        # Max allowed drawdown from peak
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

        product = Product.KELP
        position = state.position.get(product, 0)
        order_depth = state.order_depths[product]
        orders = []

        # Safely get market prices
        try:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_ask + best_bid) / 2
        except (ValueError, AttributeError):
            return orders

        # Update price history with volatility tracking
        hist = self.historical_data.setdefault(product, {
            'prices': [],
            'highs': [],
            'lows': [],
            'atr': []
        })

        hist['prices'].append(mid_price)
        # Simplified high/low for demonstration
        hist['highs'].append(mid_price)
        hist['lows'].append(mid_price)

        # Maintain volatility window
        hist['prices'] = hist['prices'][-params["window_size"]:]
        hist['highs'] = hist['highs'][-params["volatility_window"]:]
        hist['lows'] = hist['lows'][-params["volatility_window"]:]

        # Calculate volatility (ATR)
        if len(hist['prices']) >= params["volatility_window"]:
            true_ranges = [
                max(hist['highs'][i] - hist['lows'][i],
                    abs(hist['highs'][i] - hist['prices'][i-1]),
                    abs(hist['lows'][i] - hist['prices'][i-1]))
                for i in range(1, len(hist['prices']))
            ]
            atr = np.mean(true_ranges) if true_ranges else 0
            hist['atr'].append(atr)
        else:
            atr = 0

        # Dynamic spread calculation
        spread = params["base_spread"] + \
            (2 * atr) if atr else params["base_spread"]

        # Trend detection using EMA crossover
        if len(hist['prices']) >= 20:
            short_ema = np.mean(hist['prices'][-5:])
            long_ema = np.mean(hist['prices'][-20:])
            trend_direction = 1 if short_ema > long_ema else -1
        else:
            trend_direction = 0

        # Calculate fair value with momentum adjustment
        if len(hist['prices']) >= 2:
            momentum = np.mean(hist['prices'][-5:]) - \
                np.mean(hist['prices'][-10:-5])
            fair_price = mid_price + (momentum * trend_direction)
        else:
            fair_price = mid_price

        # Risk-aware position sizing
        position_capacity = params["max_position"] - abs(position)
        volatility_scale = 1 / (1 + 2*atr) if atr else 1
        order_size = max(
            1, int(volatility_scale * params["risk_multiplier"] * position_capacity))

        # Generate orders with dynamic pricing
        if trend_direction >= 0:  # Neutral or bullish
            bid_price = round(fair_price - spread)
            ask_price = round(fair_price + spread)
        else:  # Bearish
            bid_price = round(fair_price - spread*1.2)
            ask_price = round(fair_price + spread*0.8)

        # Ensure prices are within recent range (2032-2038 adaptation)
        bid_price = max(best_bid - 1, min(bid_price, best_ask - 1))
        ask_price = min(best_ask + 1, max(ask_price, best_bid + 1))

        # Add orders with fill probability estimation
        orders.append(Order(product, int(bid_price), order_size))
        orders.append(Order(product, int(ask_price), -order_size))

        # Add stop-loss orders
        if position != 0:
            stop_price = mid_price * (1 - params["stop_loss_pct"]/100) if position > 0 \
                else mid_price * (1 + params["stop_loss_pct"]/100)
            orders.append(Order(product, int(stop_price), -position))

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
