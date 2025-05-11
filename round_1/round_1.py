from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle
import statistics


class Trader:
    def __init__(self):
        self.kelp_vwap = []
        self.kelp_prices = []
        self.squid_ink_prices = []
        self.tick = 0

    def resin_strategy(self, product, order_depth, fair_value, width, position, position_limit) -> List[Order]:
        orders = []

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask <= fair_value - width:
                qty = min(-order_depth.sell_orders[best_ask],
                          position_limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid >= fair_value + width:
                qty = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))

        baaf = min([p for p in order_depth.sell_orders if p >
                   fair_value + width], default=fair_value + width + 1)
        bbbf = max([p for p in order_depth.buy_orders if p <
                   fair_value - width], default=fair_value - width - 1)

        buy_qty = position_limit - position
        sell_qty = position_limit + position

        if buy_qty > 0:
            orders.append(Order(product, bbbf + 1, buy_qty))
        if sell_qty > 0:
            orders.append(Order(product, baaf - 1, -sell_qty))

        return orders

    def kelp_strategy(self, product, order_depth, position, position_limit) -> List[Order]:
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            ask_vol = -order_depth.sell_orders[best_ask]
            bid_vol = order_depth.buy_orders[best_bid]
            mid_price = (best_ask + best_bid) / 2

            self.kelp_prices.append(mid_price)
            if len(self.kelp_prices) > 40:
                self.kelp_prices.pop(0)

            volatility = statistics.stdev(
                self.kelp_prices[-20:]) if len(self.kelp_prices) >= 20 else 0
            vwap_window = 8 if volatility > 4 else 16

            total_vol = ask_vol + bid_vol
            current_vwap = (best_bid * ask_vol + best_ask *
                            bid_vol) // total_vol if total_vol else int(mid_price)
            self.kelp_vwap.append({"vwap": current_vwap, "vol": total_vol})
            if len(self.kelp_vwap) > vwap_window:
                self.kelp_vwap.pop(0)

            total_weighted = sum(x["vwap"] * x["vol"] for x in self.kelp_vwap)
            total_vol = sum(x["vol"] for x in self.kelp_vwap)
            fair_value = total_weighted // total_vol if total_vol else int(
                mid_price)

            spread = best_ask - best_bid
            min_edge = max(1, int(spread * 0.3))
            take_spread = max(2, int(spread * 0.6))

            if spread >= take_spread:
                if fair_value - best_ask >= min_edge:
                    qty = min(ask_vol, position_limit - position)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))

                if best_bid - fair_value >= min_edge:
                    qty = min(bid_vol, position_limit + position)
                    if qty > 0:
                        orders.append(Order(product, best_bid, -qty))

            baaf = min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2)

            buy_qty = position_limit - position
            sell_qty = position_limit + position

            if buy_qty > 0:
                orders.append(Order(product, bbbf + 1, buy_qty))
            if sell_qty > 0:
                orders.append(Order(product, baaf - 1, -sell_qty))

        return orders

    def squid_strategy(self, product, order_depth, position, position_limit) -> List[Order]:
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            mid_price = (best_ask + best_bid) / 2
            self.squid_ink_prices.append(mid_price)
            if len(self.squid_ink_prices) > 50:
                self.squid_ink_prices.pop(0)

            if len(self.squid_ink_prices) >= 10:
                mean = statistics.mean(self.squid_ink_prices)
                stdev = statistics.stdev(self.squid_ink_prices)
                upper_band = mean + 1.2 * stdev
                lower_band = mean - 1.2 * stdev

                if best_ask < lower_band:
                    qty = min(-order_depth.sell_orders[best_ask],
                              position_limit - position)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))
                if best_bid > upper_band:
                    qty = min(
                        order_depth.buy_orders[best_bid], position_limit + position)
                    if qty > 0:
                        orders.append(Order(product, best_bid, -qty))

        return orders

    def run(self, state: TradingState):
        result = {}
        self.tick += 1

        if "RAINFOREST_RESIN" in state.order_depths:
            pos = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.resin_strategy(
                "RAINFOREST_RESIN",
                state.order_depths["RAINFOREST_RESIN"],
                fair_value=10000,
                width=1.8,
                position=pos,
                position_limit=50
            )

        if "KELP" in state.order_depths:
            pos = state.position.get("KELP", 0)
            result["KELP"] = self.kelp_strategy(
                "KELP",
                state.order_depths["KELP"],
                position=pos,
                position_limit=50
            )

        if "SQUID_INK" in state.order_depths:
            pos = state.position.get("SQUID_INK", 0)
            result["SQUID_INK"] = self.squid_strategy(
                "SQUID_INK",
                state.order_depths["SQUID_INK"],
                position=pos,
                position_limit=50
            )

        trader_data = {
            "kelp_vwap": self.kelp_vwap,
            "kelp_prices": self.kelp_prices,
            "squid_ink_prices": self.squid_ink_prices,
        }
        return result, 1, jsonpickle.encode(trader_data)
