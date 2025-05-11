"""
IMC Prosperity 3 Competition — Final Bot by [Your Name]
Improved trading bot implementing diverse strategies per asset class.
Strategies adapted from top submissions and customized for showcase.
"""

from datamodel import Order, OrderDepth, Trade, TradingState
from typing import List, Dict
import numpy as np
import pandas as pd
from collections import defaultdict
import jsonpickle

class Trader:
    def __init__(self):
        # Persistent memory across ticks
        self.price_history = defaultdict(list)
        self.entry_price_map = {}
        self.position_side_map = {}
        self.tick_counter = 0
        self.last_gradient = {}
        self.sunlight_index_history = []
        self.state_vars_to_persist = ["price_history", "entry_price_map", "position_side_map", "sunlight_index_history"]

        self.asset_limits = {
            "KELP": 50,
            "VOLCANIC_ROCK": 400,
            "SQUID_INK": 50,
            "RAINFOREST_RESIN": 50,
            "DJEMBES": 60,
            "CROISSANTS": 250,
            "JAMS": 350,
            "PICNIC_BASKET1": 60,
            "PICNIC_BASKET2": 100,
            "MAGNIFICENT_MACARONS": 75,
            "VOLCANIC_ROCK_VOUCHER_9500": 200,
            "VOLCANIC_ROCK_VOUCHER_9750": 200,
            "VOLCANIC_ROCK_VOUCHER_10000": 200,
            "VOLCANIC_ROCK_VOUCHER_10250": 200,
            "VOLCANIC_ROCK_VOUCHER_10500": 200
        }

    def run(self, state: TradingState):
        self.load_state(state.traderData)
        self.tick_counter += 1

        orders: Dict[str, List[Order]] = {}
        conversions = 0

        self.update_price_history(state)

        for symbol in state.order_depths:
            if symbol == "KELP":
                orders[symbol] = self.run_bollinger_strategy(state, symbol, window=20, std_dev=2.0)
            elif symbol == "VOLCANIC_ROCK":
                orders[symbol] = self.run_bollinger_strategy(state, symbol, window=50, std_dev=1.2)
            elif symbol.startswith("VOLCANIC_ROCK_VOUCHER_"):
                orders[symbol] = self.run_option_strategy(state, symbol)
            elif symbol == "SQUID_INK":
                orders[symbol] = self.run_extreme_strategy(state, symbol)
            elif symbol == "RAINFOREST_RESIN":
                orders[symbol] = self.run_resin_market_maker(state, symbol)
            elif symbol in ["PICNIC_BASKET1", "PICNIC_BASKET2"]:
                pb_orders = self.run_picnic_arbitrage(state)
                for k, v in pb_orders.items():
                    orders.setdefault(k, []).extend(v)
            elif symbol == "DJEMBES":
                orders[symbol] = self.run_mean_reversion(state, symbol)
            elif symbol == "CROISSANTS":
                orders[symbol] = self.run_olivia_tracking(state, symbol)
            elif symbol == "MAGNIFICENT_MACARONS":
                orders[symbol] = self.run_sunlight_strategy(state, symbol)

        trader_data = self.save_state()
        return orders, conversions, trader_data

    # ----- STRATEGY IMPLEMENTATIONS (each function handles a specific product type) -----

    def run_bollinger_strategy(self, state, symbol, window=20, std_dev=2.0) -> List[Order]:
        depth = state.order_depths[symbol]
        if len(self.price_history[symbol]) < window:
            return []

        prices = self.price_history[symbol][-window:]
        mean = np.mean(prices)
        std = np.std(prices)
        upper, lower = mean + std_dev * std, mean - std_dev * std
        position = state.position.get(symbol, 0)
        limit = self.asset_limits[symbol]
        orders = []

        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        best_bid = max(depth.buy_orders) if depth.buy_orders else None

        if best_ask and best_ask < lower and position < limit:
            qty = min(abs(depth.sell_orders[best_ask]), limit - position)
            orders.append(Order(symbol, best_ask, qty))
            self.entry_price_map[symbol] = best_ask

        if best_bid and best_bid > upper and position > -limit:
            qty = min(abs(depth.buy_orders[best_bid]), position + limit)
            orders.append(Order(symbol, best_bid, -qty))
            self.entry_price_map[symbol] = best_bid

        return orders

    def run_option_strategy(self, state, symbol) -> List[Order]:
        rock_price = self.price_history["VOLCANIC_ROCK"][-1] if "VOLCANIC_ROCK" in self.price_history and self.price_history["VOLCANIC_ROCK"] else 0
        try:
            strike = int(symbol.split("_")[-1])
        except:
            return []

        intrinsic = max(rock_price - strike, 0)
        depth = state.order_depths[symbol]
        best_bid = max(depth.buy_orders) if depth.buy_orders else None
        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        position = state.position.get(symbol, 0)
        limit = self.asset_limits[symbol]
        orders = []

        if best_ask and intrinsic >= best_ask and position < limit:
            qty = min(abs(depth.sell_orders[best_ask]), limit - position)
            orders.append(Order(symbol, best_ask, qty))
        elif best_bid and intrinsic <= best_bid and position > -limit:
            qty = min(abs(depth.buy_orders[best_bid]), position + limit)
            orders.append(Order(symbol, best_bid, -qty))

        return orders

    def run_extreme_strategy(self, state, symbol) -> List[Order]:
        if len(self.price_history[symbol]) < 50:
            return []
        recent_prices = self.price_history[symbol][-50:]
        mean = np.mean(recent_prices)
        current = recent_prices[-1]
        deviation = current - mean
        std = np.std(recent_prices)
        threshold = 2 * std
        orders = []
        depth = state.order_depths[symbol]
        position = state.position.get(symbol, 0)
        limit = self.asset_limits[symbol]

        if deviation > threshold and position > -limit:
            best_bid = max(depth.buy_orders)
            qty = min(abs(depth.buy_orders[best_bid]), position + limit)
            orders.append(Order(symbol, best_bid, -qty))
        elif deviation < -threshold and position < limit:
            best_ask = min(depth.sell_orders)
            qty = min(abs(depth.sell_orders[best_ask]), limit - position)
            orders.append(Order(symbol, best_ask, qty))

        return orders

    def run_resin_market_maker(self, state, symbol) -> List[Order]:
        depth = state.order_depths[symbol]
        fair = 10000
        spread = 2
        position = state.position.get(symbol, 0)
        orders = []

        if position < 50:
            orders.append(Order(symbol, fair - spread, 10))
        if position > -50:
            orders.append(Order(symbol, fair + spread, -10))

        return orders

    def run_picnic_arbitrage(self, state) -> Dict[str, List[Order]]:
        def get_mid(sym):
            d = state.order_depths[sym]
            return (max(d.buy_orders) + min(d.sell_orders)) / 2 if d.buy_orders and d.sell_orders else None

        mids = {s: get_mid(s) for s in ["CROISSANTS", "JAMS", "DJEMBES", "PICNIC_BASKET1", "PICNIC_BASKET2"]}
        orders = defaultdict(list)

        pb1_fair = 6 * mids["CROISSANTS"] + 3 * mids["JAMS"] + mids["DJEMBES"]
        pb2_fair = 4 * mids["CROISSANTS"] + 2 * mids["JAMS"]
        diff1 = mids["PICNIC_BASKET1"] - pb1_fair
        diff2 = mids["PICNIC_BASKET2"] - pb2_fair
        threshold = 30

        if diff1 > threshold:
            best_bid = max(state.order_depths["PICNIC_BASKET1"].buy_orders)
            orders["PICNIC_BASKET1"].append(Order("PICNIC_BASKET1", best_bid, -2))
        elif diff1 < -threshold:
            best_ask = min(state.order_depths["PICNIC_BASKET1"].sell_orders)
            orders["PICNIC_BASKET1"].append(Order("PICNIC_BASKET1", best_ask, 2))

        if diff2 > threshold:
            best_bid = max(state.order_depths["PICNIC_BASKET2"].buy_orders)
            orders["PICNIC_BASKET2"].append(Order("PICNIC_BASKET2", best_bid, -2))
        elif diff2 < -threshold:
            best_ask = min(state.order_depths["PICNIC_BASKET2"].sell_orders)
            orders["PICNIC_BASKET2"].append(Order("PICNIC_BASKET2", best_ask, 2))

        return orders

    def run_mean_reversion(self, state, symbol) -> List[Order]:
        prices = self.price_history[symbol]
        if len(prices) < 15:
            return []

        mean = np.mean(prices[-15:])
        std = np.std(prices[-15:])
        spread = 0.8 * std
        orders = []
        depth = state.order_depths[symbol]
        position = state.position.get(symbol, 0)
        limit = self.asset_limits[symbol]

        bid = round(mean - spread)
        ask = round(mean + spread)
        orders.append(Order(symbol, bid, 10))
        orders.append(Order(symbol, ask, -10))
        return orders

    def run_olivia_tracking(self, state, symbol) -> List[Order]:
        if symbol not in state.market_trades:
            return []
        trades = state.market_trades[symbol]
        olivia_trades = [t for t in trades if t.buyer == "Olivia" or t.seller == "Olivia"]
        orders = []
        position = state.position.get(symbol, 0)
        limit = self.asset_limits[symbol]
        depth = state.order_depths[symbol]
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)

        for t in olivia_trades:
            if t.buyer == "Olivia" and position < limit:
                orders.append(Order(symbol, best_ask, 10))
            elif t.seller == "Olivia" and position > -limit:
                orders.append(Order(symbol, best_bid, -10))
        return orders

    def run_sunlight_strategy(self, state, symbol) -> List[Order]:
        obs = state.observations.conversionObservations[symbol]
        self.sunlight_index_history.append(obs.sunlightIndex)
        if len(self.sunlight_index_history) < 10:
            return []
        smooth = np.convolve(self.sunlight_index_history, np.ones(10)/10, mode='valid')
        gradient = np.gradient(smooth)[-1]
        threshold = 0.01
        orders = []
        depth = state.order_depths[symbol]
        position = state.position.get(symbol, 0)
        limit = self.asset_limits[symbol]

        if gradient > threshold and position < limit:
            best_ask = min(depth.sell_orders)
            orders.append(Order(symbol, best_ask, 10))
        elif gradient < -threshold and position > -limit:
            best_bid = max(depth.buy_orders)
            orders.append(Order(symbol, best_bid, -10))
        return orders

    # ---- UTILS ----
    def update_price_history(self, state: TradingState):
        for sym, od in state.order_depths.items():
            if od.buy_orders and od.sell_orders:
                self.price_history[sym].append((max(od.buy_orders) + min(od.sell_orders)) / 2)
                self.price_history[sym] = self.price_history[sym][-200:]

    def load_state(self, trader_data: str):
        if trader_data:
            try:
                data = jsonpickle.decode(trader_data)
                for k in self.state_vars_to_persist:
                    if k in data:
                        setattr(self, k, data[k])
            except Exception as e:
                print("Failed to load state:", e)

    def save_state(self) -> str:
        try:
            return jsonpickle.encode({k: getattr(self, k) for k in self.state_vars_to_persist})
        except Exception as e:
            print("Failed to save state:", e)
            return ""
