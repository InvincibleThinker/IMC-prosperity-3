from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle
import math


class Trader:
    def __init__(self):
        self.kelp_ema_price = None
        self.kelp_vwap = []
        self.kelp_ema_alpha = 0.2  # for smoothing EMA
        self.max_soft_position = 40
        self.debug = False

    # ===== RAINFOREST_RESIN: Static Fair Value Strategy =====
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
        buy_volume = 0
        sell_volume = 0

        baaf = int(min(
            [p for p in order_depth.sell_orders if p > fair_value + width],
            default=fair_value + width + 1
        ))
        bbbf = int(max(
            [p for p in order_depth.buy_orders if p < fair_value - width],
            default=fair_value - width - 1
        ))

        if order_depth.sell_orders:
            best_ask = int(min(order_depth.sell_orders.keys()))
            if best_ask <= fair_value - width:
                quantity = min(
                    -order_depth.sell_orders[best_ask],
                    position_limit - position
                )
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_volume += quantity

        if order_depth.buy_orders:
            best_bid = int(max(order_depth.buy_orders.keys()))
            if best_bid >= fair_value + width:
                quantity = min(
                    order_depth.buy_orders[best_bid],
                    position_limit + position
                )
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_volume += quantity

        buy_quantity = position_limit - (position + buy_volume)
        if buy_quantity > 0:
            orders.append(Order(product, bbbf + 1, buy_quantity))

        sell_quantity = position_limit + (position - sell_volume)
        if sell_quantity > 0:
            orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    # ===== KELP: Adaptive EMA-based VWAP Strategy =====
    def dynamic_fair_value_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        timespan: int,
        position: int,
        position_limit: int
    ) -> List[Order]:
        orders = []
        buy_volume = 0
        sell_volume = 0

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = int(min(order_depth.sell_orders.keys()))
            best_bid = int(max(order_depth.buy_orders.keys()))

            ask_volume = -order_depth.sell_orders[best_ask]
            bid_volume = order_depth.buy_orders[best_bid]
            total_volume = ask_volume + bid_volume

            # VWAP
            current_vwap = int(
                (best_bid * ask_volume + best_ask * bid_volume) / total_volume
            ) if total_volume > 0 else (best_ask + best_bid) // 2

            # EMA Fair Value
            if self.kelp_ema_price is None:
                self.kelp_ema_price = current_vwap
            else:
                self.kelp_ema_price = int(
                    self.kelp_ema_alpha * current_vwap +
                    (1 - self.kelp_ema_alpha) * self.kelp_ema_price
                )

            fair_value = self.kelp_ema_price

            # Adaptive take width
            abs_pos = abs(position)
            base_take_width = 1.2
            take_width = base_take_width + (abs_pos / position_limit)

            # === Take Liquidity ===
            if best_ask <= fair_value - take_width and position < position_limit:
                qty = min(ask_volume, position_limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_volume += qty

            if best_bid >= fair_value + take_width and position > -position_limit:
                qty = min(bid_volume, position_limit + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_volume += qty

            # === Stop Loss / Forced Unwind ===
            stop_threshold = 3
            if position < -self.max_soft_position and best_bid < fair_value - stop_threshold:
                qty = min(bid_volume, abs(position))
                orders.append(Order(product, best_bid, -qty))
                if self.debug:
                    print(f"[STOP-LOSS] Selling {qty} at {best_bid}")

            if position > self.max_soft_position and best_ask > fair_value + stop_threshold:
                qty = min(ask_volume, abs(position))
                orders.append(Order(product, best_ask, -qty))
                if self.debug:
                    print(f"[STOP-LOSS] Buying {qty} at {best_ask}")

            # === Post Liquidity ===
            baaf = int(min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2))
            bbbf = int(max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2))

            if abs(position) < 10:
                buy_price = best_bid + 1
                sell_price = best_ask - 1
            else:
                buy_price = bbbf + 1
                sell_price = baaf - 1

            buy_qty = position_limit - (position + buy_volume)
            if buy_qty > 0:
                orders.append(Order(product, buy_price, buy_qty))

            sell_qty = position_limit + (position - sell_volume)
            if sell_qty > 0:
                orders.append(Order(product, sell_price, -sell_qty))

            if self.debug:
                print(
                    f"[{product}] FV={fair_value}, Bid={best_bid}, Ask={best_ask}, Pos={position}, TW={round(take_width, 2)}")

        return orders

    def run(self, state: TradingState):
        result = {}

        if "RAINFOREST_RESIN" in state.order_depths:
            pos = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.fixed_fair_value_orders(
                "RAINFOREST_RESIN",
                state.order_depths["RAINFOREST_RESIN"],
                fair_value=10000,
                width=2,
                position=pos,
                position_limit=50
            )

        if "KELP" in state.order_depths:
            pos = state.position.get("KELP", 0)
            result["KELP"] = self.dynamic_fair_value_orders(
                "KELP",
                state.order_depths["KELP"],
                timespan=10,
                position=pos,
                position_limit=50
            )

        trader_data = {
            "kelp_ema_price": self.kelp_ema_price,
            "kelp_vwap": self.kelp_vwap,
        }

        return result, 1, jsonpickle.encode(trader_data)
