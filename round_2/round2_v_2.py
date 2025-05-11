import math
from typing import List, Dict, Any
import json
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
        Product.CROISSANT: (4304, 4336),
        Product.JAM: (6618, 6690),
        Product.DJEMBE: (13419, 13502),
        Product.PICNIC_BASKET1: (59130, 59783),
        Product.PICNIC_BASKET2: (30475, 30800),
    }

    def __init__(self):
        self.window = 20
        self.price_history = {
            Product.CROISSANT: [],
            Product.JAM: [],
            Product.DJEMBE: [],
        }

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        result = {}

        mids = {
            symbol: self.get_mid_price(
                state.order_depths.get(symbol, OrderDepth())
            )
            for symbol in self.POSITION_LIMITS
        }

        # Update price history
        for symbol in self.price_history:
            mid = mids.get(symbol)
            if mid:
                self.price_history[symbol].append(mid)
                if len(self.price_history[symbol]) > self.window:
                    self.price_history[symbol].pop(0)

        # --- Basket Fair Values ---
        fair_basket1 = (
            6 * mids[Product.CROISSANT]
            + 3 * mids[Product.JAM]
            + 1 * mids[Product.DJEMBE]
        )
        fair_basket2 = (
            4 * mids[Product.CROISSANT]
            + 2 * mids[Product.JAM]
        )
        if Product.RAINFOREST_RESIN in state.order_depths:
            result[Product.RAINFOREST_RESIN] = self.trade_resin(state)
        # --- Basket Market Making ---
        result[Product.PICNIC_BASKET1] = self.market_make(
            Product.PICNIC_BASKET1, fair_basket1, state.order_depths[
                Product.PICNIC_BASKET1], state.position
        )
        result[Product.PICNIC_BASKET2] = self.market_make(
            Product.PICNIC_BASKET2, fair_basket2, state.order_depths[
                Product.PICNIC_BASKET2], state.position
        )

        # --- Individual Strategy: CROISSANT, JAM, DJEMBE ---
        for product in [Product.CROISSANT, Product.JAM, Product.DJEMBE]:
            orders = []
            if len(self.price_history[product]) >= self.window:
                mid = mids[product]
                history = self.price_history[product]
                mean = sum(history) / len(history)
                std = self.std_dev(history, mean)
                z = (mid - mean) / std if std > 0 else 0

                lower, upper = self.PRICE_RANGES[product]

                if z < -1.2 or mid < lower + 3:
                    # Mean reversion buy or breakout up from low
                    orders += self.take_best_order(
                        product, state.order_depths[product], is_buy=True, max_qty=5)
                elif z > 1.2 or mid > upper - 3:
                    # Mean reversion sell or breakout down from high
                    orders += self.take_best_order(
                        product, state.order_depths[product], is_buy=False, max_qty=5)
                else:
                    # Default market making
                    orders += self.market_make(product, mean,
                                               state.order_depths[product], state.position)

            result[product] = orders
        logger.flush(state, result, 0, "")
        return result, 0, ""

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
