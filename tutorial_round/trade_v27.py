from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle


class Trader:
    def __init__(self):
        self.kelp_vwap = []
        self.tick = 0

    def resin_strategy(self, product, order_depth, fair_value, width, position, position_limit) -> List[Order]:
        orders = []
        buy_volume = sell_volume = 0

        # More aggressive on early opportunity
        adaptive_width = width * 0.9 if self.tick < 50 else width

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask <= fair_value - adaptive_width:
                qty = min(-order_depth.sell_orders[best_ask],
                          position_limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_volume += qty

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid >= fair_value + adaptive_width:
                qty = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_volume += qty

        # Passive quote placement, more aggressive near fair value
        baaf = min([p for p in order_depth.sell_orders if p > fair_value +
                   adaptive_width], default=fair_value + adaptive_width + 1)
        bbbf = max([p for p in order_depth.buy_orders if p < fair_value -
                   adaptive_width], default=fair_value - adaptive_width - 1)

        buy_qty = position_limit - (position + buy_volume)
        if buy_qty > 0:
            orders.append(Order(product, int(bbbf + 1), buy_qty))

        sell_qty = position_limit + (position - sell_volume)
        if sell_qty > 0:
            orders.append(Order(product, int(baaf - 1), -sell_qty))

        return orders

    def kelp_strategy(self, product, order_depth, timespan, position, position_limit, take_spread=3, min_edge=2) -> List[Order]:
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            ask_vol = -order_depth.sell_orders[best_ask]
            bid_vol = order_depth.buy_orders[best_bid]
            total_vol = ask_vol + bid_vol

            current_vwap = (best_bid * ask_vol + best_ask *
                            bid_vol) // total_vol if total_vol else (best_ask + best_bid) // 2
            self.kelp_vwap.append({"vwap": current_vwap, "vol": total_vol})
            if len(self.kelp_vwap) > timespan:
                self.kelp_vwap.pop(0)

            total_weighted = sum(x["vwap"] * x["vol"] for x in self.kelp_vwap)
            total_vol = sum(x["vol"] for x in self.kelp_vwap)
            fair_value = total_weighted // total_vol if total_vol else (
                best_ask + best_bid) // 2

            if self.tick < timespan:
                fair_value = (best_ask + best_bid) // 2

            spread = best_ask - best_bid
            if spread >= take_spread:
                if best_ask <= fair_value - min_edge:
                    qty = min(ask_vol, position_limit - position)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))
                if best_bid >= fair_value + min_edge:
                    qty = min(bid_vol, position_limit + position)
                    if qty > 0:
                        orders.append(Order(product, best_bid, -qty))

            baaf = min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2)

            if (position_limit - position) > 0:
                orders.append(
                    Order(product, bbbf + 1, position_limit - position))
            if (position_limit + position) > 0:
                orders.append(Order(product, baaf - 1, -
                              (position_limit + position)))

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
                timespan=12,
                position=pos,
                position_limit=50,
                take_spread=3,
                min_edge=2
            )

        trader_data = {"kelp_vwap": self.kelp_vwap}
        return result, 1, jsonpickle.encode(trader_data)
