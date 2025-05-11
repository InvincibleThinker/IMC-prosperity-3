from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import jsonpickle
import numpy as np
from statistics import mean


class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    SQUID_INK = "SQUID_INK"


PARAMS = {
    Product.RAINFOREST_RESIN: {
        "fair_value": 10000,
        "take_width": 1,
        "clear_width": 0.5,
        "volume_limit": 0,
    },
    Product.KELP: {
        "take_width": 1,
        "clear_width": 0.5,
        "prevent_adverse": True,
        "adverse_volume": 15,
        "reversion_beta": -0.229,
        "min_edge": 2,
        "window_size": 5,
        "init_fair_value": 2033
    },
    Product.SQUID_INK: {
        "make_edge": 2,
        "min_edge": 1,
        "init_edge": 2,
        "volume_avg_window": 5,
        "volume_bar": 75,
        "edge_step": 0.5,
        "decay_factor": 0.8,
        "price_range": (1840, 1985),
        "window_size": 10
    }
}


class Trader:
    def __init__(self, params=None):
        if params is None:
            params = PARAMS
        self.params = params

        self.LIMIT = {
            Product.RAINFOREST_RESIN: 50,
            Product.KELP: 50,
            Product.SQUID_INK: 50
        }

        self.squid_data = {
            "edge": self.params[Product.SQUID_INK]["init_edge"],
            "volume_history": [],
            "price_history": []
        }

        self.kelp_data = {
            "fair_value": PARAMS[Product.KELP]["init_fair_value"],
            "price_history": []
        }

    def take_best_orders(self, product, fair_value, take_width, orders, order_depth, position):
        buy_vol = 0
        sell_vol = 0
        position_limit = self.LIMIT[product]

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            if best_ask <= fair_value - take_width:
                quantity = min(-order_depth.sell_orders[best_ask],
                               position_limit - position)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_vol += quantity

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            if best_bid >= fair_value + take_width:
                quantity = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_vol += quantity

        return buy_vol, sell_vol

    def market_make(self, product, orders, bid, ask, position, buy_vol, sell_vol):
        pos_limit = self.LIMIT[product]

        available_buy = pos_limit - (position + buy_vol)
        if available_buy > 0:
            orders.append(Order(product, round(bid), available_buy))

        available_sell = pos_limit + (position - sell_vol)
        if available_sell > 0:
            orders.append(Order(product, round(ask), -available_sell))

        return buy_vol, sell_vol

    # Rainforest Resin Strategy
    def resin_strategy(self, order_depth, position):
        params = self.params[Product.RAINFOREST_RESIN]
        orders = []

        buy_vol, sell_vol = self.take_best_orders(
            Product.RAINFOREST_RESIN,
            params["fair_value"],
            params["take_width"],
            orders,
            order_depth,
            position
        )

        spread = 2
        bid = params["fair_value"] - spread//2
        ask = params["fair_value"] + spread//2

        self.market_make(Product.RAINFOREST_RESIN, orders,
                         bid, ask, position, buy_vol, sell_vol)
        return orders

    # Kelp Strategy
    def kelp_fair_value(self, order_depth):
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_ask + best_bid) / 2
            self.kelp_data["price_history"].append(mid_price)

            if len(self.kelp_data["price_history"]) > self.params[Product.KELP]["window_size"]:
                self.kelp_data["price_history"].pop(0)

            if len(self.kelp_data["price_history"]) >= 2:
                last_price = self.kelp_data["price_history"][-2]
                returns = (mid_price - last_price) / last_price
                pred_returns = returns * \
                    self.params[Product.KELP]["reversion_beta"]
                return mid_price + (mid_price * pred_returns)

        return self.kelp_data["fair_value"]

    def kelp_strategy(self, order_depth, position):
        params = self.params[Product.KELP]
        orders = []
        fair_value = self.kelp_fair_value(order_depth)

        buy_vol, sell_vol = self.take_best_orders(
            Product.KELP,
            fair_value,
            params["take_width"],
            orders,
            order_depth,
            position
        )

        spread = params["min_edge"] * 2
        bid = fair_value - params["min_edge"]
        ask = fair_value + params["min_edge"]

        self.market_make(Product.KELP, orders, bid, ask,
                         position, buy_vol, sell_vol)
        return orders

    # Squid Ink Strategy
    def update_squid_edge(self, position):
        self.squid_data["volume_history"].append(abs(position))
        if len(self.squid_data["volume_history"]) > self.params[Product.SQUID_INK]["volume_avg_window"]:
            self.squid_data["volume_history"].pop(0)

        if len(self.squid_data["volume_history"]) == self.params[Product.SQUID_INK]["volume_avg_window"]:
            avg_volume = mean(self.squid_data["volume_history"])

            if avg_volume >= self.params[Product.SQUID_INK]["volume_bar"]:
                self.squid_data["edge"] += self.params[Product.SQUID_INK]["edge_step"]
            else:
                new_edge = self.squid_data["edge"] * \
                    self.params[Product.SQUID_INK]["decay_factor"]
                if new_edge >= self.params[Product.SQUID_INK]["min_edge"]:
                    self.squid_data["edge"] = new_edge

    def squid_strategy(self, order_depth, position):
        params = self.params[Product.SQUID_INK]
        orders = []

        self.update_squid_edge(position)

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            fair_value = (best_ask + best_bid) / 2
        else:
            fair_value = mean(params["price_range"])

        take_width = self.squid_data["edge"]
        buy_vol, sell_vol = self.take_best_orders(
            Product.SQUID_INK,
            fair_value,
            take_width,
            orders,
            order_depth,
            position
        )

        bid = fair_value - self.squid_data["edge"]
        ask = fair_value + self.squid_data["edge"]

        bid = max(bid, params["price_range"][0])
        ask = min(ask, params["price_range"][1])

        self.market_make(Product.SQUID_INK, orders, bid,
                         ask, position, buy_vol, sell_vol)
        return orders

    def run(self, state: TradingState):
        result = {}

        if Product.RAINFOREST_RESIN in state.order_depths:
            position = state.position.get(Product.RAINFOREST_RESIN, 0)
            result[Product.RAINFOREST_RESIN] = self.resin_strategy(
                state.order_depths[Product.RAINFOREST_RESIN],
                position
            )

        if Product.KELP in state.order_depths:
            position = state.position.get(Product.KELP, 0)
            result[Product.KELP] = self.kelp_strategy(
                state.order_depths[Product.KELP],
                position
            )

        if Product.SQUID_INK in state.order_depths:
            position = state.position.get(Product.SQUID_INK, 0)
            result[Product.SQUID_INK] = self.squid_strategy(
                state.order_depths[Product.SQUID_INK],
                position
            )

        return result, 0, ""
