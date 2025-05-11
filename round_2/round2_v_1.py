import json
import numpy as np
import pandas as pd
import jsonpickle
from typing import Dict, List, Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


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
    # New picnic products
    CROISSANT = "CROISSANT"
    JAM = "JAM"
    DJEMBE = "DJEMBE"
    PICNIC_BASKET1 = "PICNIC_BASKET1"
    PICNIC_BASKET2 = "PICNIC_BASKET2"

    # Existing products
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    SQUID_INK = "SQUID_INK"


class StrategyParams:
    # Picnic Basket Parameters
    PICNIC = {
        "basket1_components": {
            Product.CROISSANT: 6,
            Product.JAM: 3,
            Product.DJEMBE: 1
        },
        "basket2_components": {
            Product.CROISSANT: 4,
            Product.JAM: 2
        },
        "spread_window": 20,
        "zscore_threshold": 2.0,
        "position_limits": {
            Product.PICNIC_BASKET1: 60,
            Product.PICNIC_BASKET2: 100,
            Product.CROISSANT: 250,
            Product.JAM: 350,
            Product.DJEMBE: 60
        },
        "max_order_size": 5
    }

    # Existing parameters remain unchanged
    RESIN = {"fair_value": 10000, "take_width": 2,
             "spread": 2, "position_limit": 50}
    KELP = {"take_width": 1.2, "min_edge": 1.0, "reversion_beta": -
            0.45, "window_size": 7, "position_limit": 50}
    SQUID = {"pair_symbol": "KELP", "hedge_ratio": 1.0,
             "volatility_window": 20, "stop_loss": 2.1, "position_limit": 50}


class Trader:
    def __init__(self):
        self.position_limits = {
            # Picnic products
            Product.PICNIC_BASKET1: 60,
            Product.PICNIC_BASKET2: 100,
            Product.CROISSANT: 250,
            Product.JAM: 350,
            Product.DJEMBE: 60,
            # Existing products
            Product.RAINFOREST_RESIN: 50,
            Product.KELP: 50,
            Product.SQUID_INK: 50,

        }

        self.historical_data = {
            Product.KELP: {'timestamps': [], 'mid_prices': []},
            Product.SQUID_INK: {'timestamps': [], 'spreads': []},
            Product.PICNIC_BASKET1: {'spread_history': []},
            Product.PICNIC_BASKET2: {'spread_history': []}
        }

    def run(self, state: TradingState):
        result = {}
        trader_data = jsonpickle.decode(
            state.traderData) if state.traderData else {}

        try:
            # Existing strategies
            if Product.RAINFOREST_RESIN in state.order_depths:
                result[Product.RAINFOREST_RESIN] = self.trade_resin(state)
            if Product.KELP in state.order_depths:
                result[Product.KELP] = self.trade_kelp(state, trader_data)
            if Product.SQUID_INK in state.order_depths:
                result[Product.SQUID_INK] = self.trade_squid(state)

            # New Picnic Basket strategies
            result.update(self.trade_picnic_baskets(state, trader_data))

            # Update trader_data with historical data
            trader_data['historical_data'] = self.historical_data

        except Exception as e:
            logger.print(f"Error: {str(e)}")

        logger.flush(state, result, 0, jsonpickle.encode(trader_data))
        return result, 0, jsonpickle.encode(trader_data)

    def trade_picnic_baskets(self, state: TradingState, trader_data: dict) -> Dict[str, List[Order]]:
        orders = {}
        params = StrategyParams.PICNIC

        # Process both picnic baskets
        for basket, components in [(Product.PICNIC_BASKET1, params["basket1_components"]),
                                   (Product.PICNIC_BASKET2, params["basket2_components"])]:

            if basket not in state.order_depths:
                continue

            # Get current positions
            basket_pos = state.position.get(basket, 0)
            component_positions = {product: state.position.get(product, 0)
                                   for product in components.keys()}

            # Calculate synthetic price
            synthetic_price = self.calculate_synthetic_price(
                state.order_depths, components)
            basket_price = self.get_mid_price(state.order_depths[basket])

            if synthetic_price is None or basket_price is None:
                continue

            spread = basket_price - synthetic_price

            # Update spread history
            spread_history = self.historical_data[basket]['spread_history']
            spread_history.append(spread)
            if len(spread_history) > params["spread_window"]:
                spread_history.pop(0)

            # Calculate z-score
            if len(spread_history) >= params["spread_window"]:
                spread_mean = np.mean(spread_history)
                spread_std = np.std(spread_history)
                zscore = (spread - spread_mean) / spread_std

                # Generate orders if beyond threshold
                if abs(zscore) > params["zscore_threshold"]:
                    basket_orders, component_orders = self.generate_arb_orders(
                        state, basket, components, basket_pos, spread, zscore, params
                    )

                    if basket_orders:
                        orders[basket] = basket_orders
                    for product, product_orders in component_orders.items():
                        if product not in orders:
                            orders[product] = []
                        orders[product].extend(product_orders)

        return orders

    def calculate_synthetic_price(self, order_depths: Dict[str, OrderDepth], components: Dict[str, int]) -> float:
        synthetic = 0
        for product, quantity in components.items():
            if product not in order_depths:
                return None
            depth = order_depths[product]
            if not depth.buy_orders or not depth.sell_orders:
                return None
            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())
            synthetic += (best_bid + best_ask) / 2 * quantity
        return synthetic

    def generate_arb_orders(self, state: TradingState, basket: str, components: Dict[str, int],
                            position: int, spread: float, zscore: float, params: dict):
        basket_orders = []
        component_orders = {}

        # Determine trade direction
        if zscore > params["zscore_threshold"]:
            # Sell basket, buy components
            best_bid = max(state.order_depths[basket].buy_orders.keys())
            qty = min(params["max_order_size"],
                      self.position_limits[basket] + position)
            basket_orders.append(Order(basket, best_bid, -qty))

            # Buy components
            for product, quantity in components.items():
                depth = state.order_depths[product]
                best_ask = min(depth.sell_orders.keys())
                comp_qty = quantity * qty
                comp_qty = min(
                    comp_qty, self.position_limits[product] - state.position.get(product, 0))
                if comp_qty > 0:
                    if product not in component_orders:
                        component_orders[product] = []
                    component_orders[product].append(
                        Order(product, best_ask, comp_qty))

        elif zscore < -params["zscore_threshold"]:
            # Buy basket, sell components
            best_ask = min(state.order_depths[basket].sell_orders.keys())
            qty = min(params["max_order_size"],
                      self.position_limits[basket] - position)
            basket_orders.append(Order(basket, best_ask, qty))

            # Sell components
            for product, quantity in components.items():
                depth = state.order_depths[product]
                best_bid = max(depth.buy_orders.keys())
                comp_qty = quantity * qty
                comp_qty = min(
                    comp_qty, self.position_limits[product] + state.position.get(product, 0))
                if comp_qty > 0:
                    if product not in component_orders:
                        component_orders[product] = []
                    component_orders[product].append(
                        Order(product, best_bid, -comp_qty))

        return basket_orders, component_orders

    # Existing strategies remain unchanged below
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

    def get_mid_price(self, order_depth: OrderDepth) -> float:
        bids = order_depth.buy_orders.keys()
        asks = order_depth.sell_orders.keys()
        return (min(asks) + max(bids)) / 2 if bids and asks else None
