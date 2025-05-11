from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle
import statistics


class Trader:
    def __init__(self):
        self.kelp_vwap = []
        self.kelp_prices = []
        self.squid_vwap = []
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
                qty = min(order_depth.buy_orders[best_bid],
                          position_limit + position)
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

    def vwap_strategy(self, product, order_depth, position, position_limit, price_list, vwap_data) -> List[Order]:
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            ask_vol = -order_depth.sell_orders[best_ask]
            bid_vol = order_depth.buy_orders[best_bid]
            mid_price = (best_ask + best_bid) / 2

            price_list.append(mid_price)
            if len(price_list) > 40:
                price_list.pop(0)

            volatility = statistics.stdev(
                price_list[-20:]) if len(price_list) >= 20 else 0
            vwap_window = 8 if volatility > 4 else 16

            total_vol = ask_vol + bid_vol
            current_vwap = (best_bid * ask_vol + best_ask *
                            bid_vol) // total_vol if total_vol else int(mid_price)
            vwap_data.append({"vwap": current_vwap, "vol": total_vol})
            if len(vwap_data) > vwap_window:
                vwap_data.pop(0)

            total_weighted = sum(x["vwap"] * x["vol"] for x in vwap_data)
            total_vol = sum(x["vol"] for x in vwap_data)
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

    def run(self, state: TradingState):
        result = {}
        self.tick += 1

        if "KELP" in state.order_depths:
            kelp_pos = state.position.get("KELP", 0)
            result["KELP"] = self.vwap_strategy(
                "KELP", state.order_depths["KELP"], kelp_pos, 50, self.kelp_prices, self.kelp_vwap)

        if "SQUID_INK" in state.order_depths:
            squid_pos = state.position.get("SQUID_INK", 0)
            result["SQUID_INK"] = self.vwap_strategy(
                "SQUID_INK", state.order_depths["SQUID_INK"], squid_pos, 50, self.squid_ink_prices, self.squid_vwap)

        if "RAINFOREST_RESIN" in state.order_depths:
            resin_pos = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.resin_strategy(
                "RAINFOREST_RESIN", state.order_depths["RAINFOREST_RESIN"], 10000, 1.8, resin_pos, 50)

        return result, 1, ""
