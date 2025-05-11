from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle
import statistics


class Trader:
    def __init__(self):
        self.kelp_prices = []
        self.tick = 0
        self.max_history = 20  # for z-score window

    def resin_strategy(self, product, order_depth, fair_value, width, position, position_limit) -> List[Order]:
        orders = []
        buy_volume = sell_volume = 0

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask <= fair_value - width:
                qty = min(-order_depth.sell_orders[best_ask],
                          position_limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_volume += qty

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid >= fair_value + width:
                qty = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_volume += qty

        baaf = min([p for p in order_depth.sell_orders if p >
                   fair_value + width], default=fair_value + width + 1)
        bbbf = max([p for p in order_depth.buy_orders if p <
                   fair_value - width], default=fair_value - width - 1)

        buy_qty = position_limit - (position + buy_volume)
        if buy_qty > 0:
            orders.append(Order(product, bbbf + 1, buy_qty))

        sell_qty = position_limit + (position - sell_volume)
        if sell_qty > 0:
            orders.append(Order(product, baaf - 1, -sell_qty))

        return orders

    def kelp_zscore_strategy(self, product, order_depth, position, position_limit, z_entry=1.5, z_exit=0.3) -> List[Order]:
        orders = []
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            mid_price = (best_ask + best_bid) / 2
            self.kelp_prices.append(mid_price)

            if len(self.kelp_prices) > self.max_history:
                self.kelp_prices.pop(0)

            if len(self.kelp_prices) >= self.max_history:
                mean = statistics.mean(self.kelp_prices)
                std = statistics.stdev(self.kelp_prices)
                if std == 0:
                    return orders

                z_score = (mid_price - mean) / std

                # Buy signal
                if z_score < -z_entry:
                    buy_price = best_bid + 1
                    volume = min(position_limit - position,
                                 order_depth.buy_orders[best_bid])
                    if volume > 0:
                        orders.append(Order(product, buy_price, volume))

                # Sell signal
                elif z_score > z_entry:
                    sell_price = best_ask - 1
                    volume = min(position + position_limit, -
                                 order_depth.sell_orders[best_ask])
                    if volume > 0:
                        orders.append(Order(product, sell_price, -volume))

                # Exit condition (close positions)
                elif abs(z_score) < z_exit:
                    # Close long
                    if position > 0:
                        orders.append(Order(product, best_bid, -position))
                    # Close short
                    elif position < 0:
                        orders.append(Order(product, best_ask, -position))

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
            result["KELP"] = self.kelp_zscore_strategy(
                "KELP",
                state.order_depths["KELP"],
                position=pos,
                position_limit=50,
                z_entry=1.6,
                z_exit=0.3
            )

        trader_data = {"kelp_prices": self.kelp_prices}
        return result, 1, jsonpickle.encode(trader_data)
