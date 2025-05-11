from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle
import math

# here position limit is 50 for both products
# this is giving profit of 4625887.78234863 in pnl


class Trader:
    def __init__(self):
        self.starfruit_prices = []
        self.starfruit_vwap = []
        self.kelp_prices = []
        self.kelp_vwap = []

    # ========== Fixed Fair Value Strategy (RAINFOREST_RESIN) ==========
    def fixed_fair_value_orders(self, product: str, order_depth: OrderDepth,
                                fair_value: int, width: int, position: int,
                                position_limit: int) -> List[Order]:
        orders = []
        buy_order_volume = 0
        sell_order_volume = 0

        # Calculate aggressive price levels with integer conversion
        baaf = int(min([p for p in order_depth.sell_orders if p >
                   fair_value + 1], default=fair_value + 2))
        bbbf = int(max([p for p in order_depth.buy_orders if p <
                   fair_value - 1], default=fair_value - 2))

        # Take liquidity
        if order_depth.sell_orders:
            best_ask = int(min(order_depth.sell_orders.keys()))
            if best_ask < fair_value:
                quantity = min(-order_depth.sell_orders[best_ask],
                               position_limit - position)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity

        if order_depth.buy_orders:
            best_bid = int(max(order_depth.buy_orders.keys()))
            if best_bid > fair_value:
                quantity = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity

        # Post liquidity with integer prices
        buy_quantity = position_limit - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, bbbf + 1, buy_quantity))

        sell_quantity = position_limit + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    # ========== Dynamic VWAP Strategy (KELP) ==========
    def dynamic_fair_value_orders(self, product: str, order_depth: OrderDepth,
                                  timespan: int, position: int, position_limit: int,
                                  take_width: float = 1.0) -> List[Order]:
        orders = []
        buy_order_volume = 0
        sell_order_volume = 0

        if order_depth.sell_orders and order_depth.buy_orders:
            # Get integer prices
            best_ask = int(min(order_depth.sell_orders.keys()))
            best_bid = int(max(order_depth.buy_orders.keys()))

            # Calculate current VWAP
            ask_volume = -order_depth.sell_orders[best_ask]
            bid_volume = order_depth.buy_orders[best_bid]
            total_volume = ask_volume + bid_volume

            current_vwap = int(
                (best_bid * ask_volume + best_ask * bid_volume) / total_volume)

            # Update price history
            price_history = self.kelp_prices if product == "KELP" else self.starfruit_prices
            vwap_history = self.kelp_vwap if product == "KELP" else self.starfruit_vwap

            price_history.append((best_ask + best_bid) // 2)
            vwap_history.append({"vol": total_volume, "vwap": current_vwap})

            # Trim history to timespan
            while len(vwap_history) > timespan:
                price_history.pop(0)
                vwap_history.pop(0)

            # Calculate weighted fair value as integer
            total_vol = sum(x["vol"] for x in vwap_history)
            if total_vol > 0:
                fair_value = int(sum(x["vwap"] * x["vol"]
                                 for x in vwap_history) / total_vol)
            else:
                fair_value = current_vwap

            # Take liquidity with integer prices
            if best_ask <= fair_value - take_width:
                quantity = min(ask_volume, position_limit - position)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity

            if best_bid >= fair_value + take_width:
                quantity = min(bid_volume, position_limit + position)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity

            # Post liquidity with integer prices
            baaf = int(min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2))
            bbbf = int(max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2))

            buy_quantity = position_limit - (position + buy_order_volume)
            if buy_quantity > 0:
                orders.append(Order(product, bbbf + 1, buy_quantity))

            sell_quantity = position_limit + (position - sell_order_volume)
            if sell_quantity > 0:
                orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    def run(self, state: TradingState):
        result = {}

        # RAINFOREST_RESIN (Fixed Fair Value)
        if "RAINFOREST_RESIN" in state.order_depths:
            position = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.fixed_fair_value_orders(
                product="RAINFOREST_RESIN",
                order_depth=state.order_depths["RAINFOREST_RESIN"],
                fair_value=10000,
                width=2,
                position=position,
                position_limit=50
            )

        # KELP (Dynamic VWAP)
        if "KELP" in state.order_depths:
            position = state.position.get("KELP", 0)
            result["KELP"] = self.dynamic_fair_value_orders(
                product="KELP",
                order_depth=state.order_depths["KELP"],
                timespan=10,
                position=position,
                position_limit=50,
                take_width=1.5
            )

        # Serialize custom data
        trader_data = {
            "starfruit_prices": self.starfruit_prices,
            "starfruit_vwap": self.starfruit_vwap,
            "kelp_prices": self.kelp_prices,
            "kelp_vwap": self.kelp_vwap
        }

        return result, 1, jsonpickle.encode(trader_data)
