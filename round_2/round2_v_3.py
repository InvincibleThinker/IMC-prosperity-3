import math
from typing import List, Dict, Any
import json
import numpy as np
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
    CROISSANT = "CROISSANTS"
    JAM = "JAMS"
    DJEMBE = "DJEMBES"
    PICNIC_BASKET1 = "PICNIC_BASKET1"
    PICNIC_BASKET2 = "PICNIC_BASKET2"

    # Existing products
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


class BlackScholes:
    def __init__(self, S: float, K: float, T: float, r: float, sigma: float):
        self.S = S
        self.K = K
        self.T = T
        self.r = r
        self.sigma = sigma

    def d1(self):
        return (math.log(self.S / self.K) + (self.r + 0.5 * self.sigma**2) * self.T) / (self.sigma * math.sqrt(self.T))

    def d2(self):
        return self.d1() - self.sigma * math.sqrt(self.T)

    def call_price(self):
        d1, d2 = self.d1(), self.d2()
        return self.S * self.N(d1) - self.K * math.exp(-self.r * self.T) * self.N(d2)

    def put_price(self):
        d1, d2 = self.d1(), self.d2()
        return self.K * math.exp(-self.r * self.T) * self.N(-d2) - self.S * self.N(-d1)

    def delta(self, option_type='call'):
        d1 = self.d1()
        return self.N(d1) if option_type == 'call' else self.N(d1) - 1

    def gamma(self):
        d1 = self.d1()
        return self.n(d1) / (self.S * self.sigma * math.sqrt(self.T))

    def vega(self):
        d1 = self.d1()
        return self.S * self.n(d1) * math.sqrt(self.T)

    def implied_volatility(self, option_price, option_type='call', tol=1e-5, max_iter=100):
        sigma = 0.5
        for _ in range(max_iter):
            self.sigma = sigma
            price = self.call_price() if option_type == 'call' else self.put_price()
            vega = self.vega()
            if vega == 0:
                return sigma
            diff = price - option_price
            if abs(diff) < tol:
                return sigma
            sigma -= diff / vega
        return sigma

    def N(self, x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def n(self, x):
        return math.exp(-0.5 * x**2) / math.sqrt(2 * math.pi)


class Trader:
    POSITION_LIMITS = {
        Product.CROISSANT: 250,
        Product.JAM: 350,
        Product.DJEMBE: 60,
        Product.PICNIC_BASKET1: 60,
        Product.PICNIC_BASKET2: 100,
    }

    PRICE_RANGES = {
        Product.CROISSANT: (4304.5, 4338.5),
        Product.JAM: (6615.5, 6702.5),
        Product.DJEMBE: (13422.5, 13506.5),
        Product.PICNIC_BASKET1: (59123.5, 59776.5),
        Product.PICNIC_BASKET2: (30471.0, 30800.5),
    }

    def __init__(self):
        self.window = 50  # Increased from 20 for more stable signals
        self.price_history = {
            Product.CROISSANT: [],
            Product.JAM: [],
            Product.DJEMBE: [],
            Product.PICNIC_BASKET1: [],
            Product.PICNIC_BASKET2: []
        }
        self.spread_history = {
            Product.PICNIC_BASKET1: [],
            Product.PICNIC_BASKET2: []
        }

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        result = {}

        # Calculate mid prices for all products
        mids = self.calculate_all_mids(state.order_depths)

        # Update price history and calculate volatilities
        volatilities = self.update_histories_and_calc_volatility(mids)

        # Basket trading with improved risk management
        basket_orders = self.trade_baskets(state, mids, volatilities)
        result.update(basket_orders)

        # Individual component strategies
        component_orders = self.trade_components(state, mids, volatilities)
        result.update(component_orders)

        # Existing resin strategy
        if Product.RAINFOREST_RESIN in state.order_depths:
            result[Product.RAINFOREST_RESIN] = self.trade_resin(state)

        logger.flush(state, result, 0, "")
        return result, 0, ""

    def trade_baskets(self, state, mids, volatilities):
        orders = {}
        basket_params = {
            Product.PICNIC_BASKET1: {
                'components': [Product.CROISSANT, Product.JAM, Product.DJEMBE],
                'weights': [6, 3, 1],
                'vol_scale_factor': 0.8
            },
            Product.PICNIC_BASKET2: {
                'components': [Product.CROISSANT, Product.JAM],
                'weights': [4, 2],
                'vol_scale_factor': 0.6  # More conservative for PICNIC_BASKET2
            }
        }

        for basket, params in basket_params.items():

            # Avoid trading if close to position limit
            basket_volatility = volatilities.get(basket, 0)
            vol_adjustment = 1 + basket_volatility * params['vol_scale_factor']
            position = state.position.get(basket, 0)
            limit = self.POSITION_LIMITS[basket]
            if abs(position) >= limit:
                continue
            # Calculate synthetic price and spread
            synthetic = sum(
                w * mids[p] for p, w in zip(params['components'], params['weights']))
            basket_mid = mids.get(basket, synthetic)
            spread = basket_mid - synthetic

            # Update spread history
            self.spread_history[basket].append(spread)
            if len(self.spread_history[basket]) > self.window:
                self.spread_history[basket].pop(0)

            # Calculate dynamic spread thresholds
            spread_mean = np.mean(self.spread_history[basket][-self.window:])
            spread_std = np.std(self.spread_history[basket][-self.window:])
            vol_adjustment = 1 + \
                volatilities.get(basket, 0) * params['vol_scale_factor']

            # Dynamic z-score thresholds
            # Shorter history for faster response
            smooth_spread = np.mean(self.spread_history[basket][-5:])
            upper_threshold = smooth_spread + spread_std * vol_adjustment
            lower_threshold = smooth_spread - spread_std * vol_adjustment

            position = state.position.get(basket, 0)
            limit = self.POSITION_LIMITS[basket]

            basket_orders = []

            if spread > spread_mean + upper_threshold * spread_std:
                # Sell basket, buy components
                qty = self.calculate_safe_quantity(limit, position, short=True)
                if qty > 0:
                    buy_orders = state.order_depths[basket].buy_orders
                    if buy_orders:
                        best_bid = max(buy_orders.keys())
                        basket_orders.append(Order(basket, best_bid, -qty))
                        orders.update(self.hedge_components(
                            params['components'], params['weights'], qty,
                            state.order_depths, state.position, buy_components=True
                        ))

            elif spread < spread_mean + lower_threshold * spread_std:
                # Buy basket, sell components
                qty = self.calculate_safe_quantity(
                    limit, position, short=False)
                if qty > 0:
                    best_ask = min(
                        state.order_depths[basket].sell_orders.keys())
                    basket_orders.append(Order(basket, best_ask, qty))
                    orders.update(self.hedge_components(
                        params['components'], params['weights'], qty,
                        state.order_depths, state.position, buy_components=False
                    ))

            if basket_orders:
                orders[basket] = basket_orders

        return orders

    def hedge_components(self, components, weights, qty, order_depths, positions, buy_components):
        component_orders = {}
        for product, weight in zip(components, weights):
            position = positions.get(product, 0)
            limit = self.POSITION_LIMITS[product]
            hedge_qty = weight * qty

            # Check for liquidity
            max_available = limit - position if buy_components else limit + position
            best_order = order_depths[product].buy_orders if buy_components else order_depths[product].sell_orders
            if best_order:
                price = max(best_order.keys()) if buy_components else min(
                    best_order.keys())
                available_qty = best_order[price]
                qty_to_order = min(hedge_qty, available_qty, max_available)

                if qty_to_order > 0:
                    component_orders[product] = [
                        Order(product, price, qty_to_order)]
        return component_orders

    def calculate_safe_quantity(self, limit, current_position, short=False, spread_z=0.0):
        max_qty = limit - current_position if not short else limit + current_position
        # Dynamic sizing based on z-score and remaining capacity
        # Up to 20% of remaining capacity
        base_qty = max(1, int(max_qty * 0.2))
        # Adjust quantity based on z-score magnitude
        z_adjusted = max(1, int(base_qty * (abs(spread_z) / 2.0)))
        return min(max_qty, z_adjusted)

    def update_histories_and_calc_volatility(self, mids):
        volatilities = {}
        for product in self.price_history:
            # Use last 10 data points for more responsive volatility
            if len(self.price_history[product]) >= 10:
                returns = np.diff(np.log(self.price_history[product][-10:]))
                volatilities[product] = np.std(
                    returns) * np.sqrt(252)  # Annualized
        return volatilities

    def trade_components(self, state, mids, volatilities):
        component_orders = {}
        for product in [Product.CROISSANT, Product.JAM, Product.DJEMBE]:
            orders = []
            history = self.price_history.get(product, [])

            if len(history) >= 20:
                # Calculate Bollinger Bands
                moving_avg = np.mean(history[-20:])
                std_dev = np.std(history[-20:])
                upper_band = moving_avg + 1.5 * std_dev
                lower_band = moving_avg - 1.5 * std_dev

                current_price = mids[product]
                position = state.position.get(product, 0)
                limit = self.POSITION_LIMITS[product]

                # Mean reversion strategy with volatility adjustment
                if current_price > upper_band:
                    sell_qty = self.calculate_safe_quantity(
                        limit, position, short=True)
                    if sell_qty > 0:
                        best_bid = max(
                            state.order_depths[product].buy_orders.keys())
                        orders.append(Order(product, best_bid, -sell_qty))
                elif current_price < lower_band:
                    buy_qty = self.calculate_safe_quantity(
                        limit, position, short=False)
                    if buy_qty > 0:
                        best_ask = min(
                            state.order_depths[product].sell_orders.keys())
                        orders.append(Order(product, best_ask, buy_qty))

            if orders:
                component_orders[product] = orders

        return component_orders

    def calculate_all_mids(self, order_depths):
        return {
            product: self.get_mid_price(
                order_depths.get(product, OrderDepth()))
            for product in self.POSITION_LIMITS
        }

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

    def std_dev(self, prices, mean):
        return math.sqrt(sum((p - mean) ** 2 for p in prices) / len(prices))

    def get_mid_price(self, order_depth: OrderDepth) -> float:
        best_ask = min(order_depth.sell_orders.keys()
                       ) if order_depth.sell_orders else float('inf')
        best_bid = max(order_depth.buy_orders.keys()
                       ) if order_depth.buy_orders else float('-inf')

        if best_ask == float('inf') and best_bid == float('-inf'):
            return 0
        elif best_ask == float('inf'):
            return best_bid
        elif best_bid == float('-inf'):
            return best_ask
        else:
            return (best_bid + best_ask) / 2

    def market_make(self, symbol: str, fair_value: float, depth: OrderDepth, position: Dict[str, int]) -> List[Order]:
        orders = []
        limit = self.POSITION_LIMITS[symbol]
        pos = position.get(symbol, 0)
        spread = 2
        buy_price = int(fair_value - spread)
        sell_price = int(fair_value + spread)

        if pos < limit:
            orders.append(Order(symbol, buy_price, 10))
        if pos > -limit:
            orders.append(Order(symbol, sell_price, -10))
        return orders

    def take_best_order(self, symbol: str, depth: OrderDepth, is_buy: bool, max_qty: int) -> List[Order]:
        orders = []
        book = depth.sell_orders if is_buy else depth.buy_orders
        sorted_book = sorted(book.items()) if is_buy else sorted(
            book.items(), reverse=True)

        for price, qty in sorted_book:
            take_qty = min(abs(qty), max_qty)
            if take_qty <= 0:
                break
            orders.append(
                Order(symbol, price, take_qty if is_buy else -take_qty))
            max_qty -= take_qty
        return orders

    def clear_position(self, symbol: str, depth: OrderDepth, position: int) -> List[Order]:
        if position == 0:
            return []
        return self.take_best_order(symbol, depth, is_buy=(position < 0), max_qty=abs(position))
