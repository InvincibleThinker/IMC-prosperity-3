from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle
import math

# this is giving profit of 4695733.17126465 in pnl


class Trader:
    def __init__(self):
        self.kelp_prices = []       # Price history for KELP
        self.kelp_vwap = []         # VWAP history for KELP

    # ========== Fixed Fair Value Strategy (RAINFOREST_RESIN) ==========
    def fixed_fair_value_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: int,
        width: int,
        position: int,
        position_limit: int
    ) -> List[Order]:
        orders = []
        buy_order_volume = 0
        sell_order_volume = 0

        # Calculate BAAF/BBBF using width parameter
        baaf = int(min(
            [p for p in order_depth.sell_orders if p > fair_value + width],
            default=fair_value + width + 1
        ))
        bbbf = int(max(
            [p for p in order_depth.buy_orders if p < fair_value - width],
            default=fair_value - width - 1
        ))

        # Take liquidity with width-based thresholds
        if order_depth.sell_orders:
            best_ask = int(min(order_depth.sell_orders.keys()))
            if best_ask <= fair_value - width:
                quantity = min(
                    -order_depth.sell_orders[best_ask],
                    position_limit - position
                )
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity

        if order_depth.buy_orders:
            best_bid = int(max(order_depth.buy_orders.keys()))
            if best_bid >= fair_value + width:
                quantity = min(
                    order_depth.buy_orders[best_bid],
                    position_limit + position
                )
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity

        # Post liquidity outside current spread
        buy_quantity = position_limit - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, bbbf + 1, buy_quantity))

        sell_quantity = position_limit + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    # ========== Dynamic VWAP Strategy (KELP) ==========
    def dynamic_fair_value_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        timespan: int,
        position: int,
        position_limit: int,
        take_width: float = 1.5
    ) -> List[Order]:
        orders = []
        buy_order_volume = 0
        sell_order_volume = 0

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = int(min(order_depth.sell_orders.keys()))
            best_bid = int(max(order_depth.buy_orders.keys()))

            # Calculate current VWAP
            ask_volume = -order_depth.sell_orders[best_ask]
            bid_volume = order_depth.buy_orders[best_bid]
            total_volume = ask_volume + bid_volume

            current_vwap = int(
                (best_bid * ask_volume + best_ask * bid_volume) / total_volume
            ) if total_volume > 0 else (best_ask + best_bid) // 2

            # Update VWAP history
            self.kelp_vwap.append({"vol": total_volume, "vwap": current_vwap})
            if len(self.kelp_vwap) > timespan:
                self.kelp_vwap.pop(0)

            # Calculate weighted fair value
            total_vol = sum(x["vol"] for x in self.kelp_vwap)
            if total_vol > 0:
                fair_value = int(
                    sum(x["vwap"] * x["vol"]
                        for x in self.kelp_vwap) / total_vol
                )
            else:
                fair_value = current_vwap

            # Take liquidity
            if best_ask <= fair_value - take_width:
                quantity = min(
                    ask_volume,
                    position_limit - position
                )
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity

            if best_bid >= fair_value + take_width:
                quantity = min(
                    bid_volume,
                    position_limit + position
                )
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity

            # Post liquidity
            baaf = int(min(
                [p for p in order_depth.sell_orders if p > fair_value + 1],
                default=fair_value + 2
            ))
            bbbf = int(max(
                [p for p in order_depth.buy_orders if p < fair_value - 1],
                default=fair_value - 2
            ))

            buy_quantity = position_limit - (position + buy_order_volume)
            if buy_quantity > 0:
                orders.append(Order(product, bbbf + 1, buy_quantity))

            sell_quantity = position_limit + (position - sell_order_volume)
            if sell_quantity > 0:
                orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    def run(self, state: TradingState):
        result = {}

        # RAINFOREST_RESIN: Fixed strategy with width=2
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

        # KELP: Dynamic VWAP strategy
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

        # Serialize data
        trader_data = {
            "kelp_vwap": self.kelp_vwap
        }
        return result, 1, jsonpickle.encode(trader_data)
