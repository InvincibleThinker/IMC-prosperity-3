from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle


class Trader:
    def __init__(self):
        self.kelp_vwap_history = []
        self.kelp_price_history = []
        self.resin_tick = 0

    def compute_vwap(self, order_depth: OrderDepth) -> float:
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        ask_vol = -order_depth.sell_orders[best_ask]
        bid_vol = order_depth.buy_orders[best_bid]
        total_vol = ask_vol + bid_vol
        return ((best_ask * bid_vol + best_bid * ask_vol) / total_vol) if total_vol > 0 else (best_ask + best_bid) / 2

    def kelp_momentum_strategy(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        position_limit: int,
        window: int = 6,
        take_threshold: float = 1.5,
        momentum_threshold: float = 0.3
    ) -> List[Order]:
        orders = []

        if not order_depth.sell_orders or not order_depth.buy_orders:
            return orders

        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        vwap_now = self.compute_vwap(order_depth)

        self.kelp_vwap_history.append(vwap_now)
        if len(self.kelp_vwap_history) > window:
            self.kelp_vwap_history.pop(0)

        # Calculate simple momentum as VWAP delta over window
        if len(self.kelp_vwap_history) >= window:
            momentum = vwap_now - self.kelp_vwap_history[0]
        else:
            momentum = 0

        buy_volume = -order_depth.sell_orders[best_ask]
        sell_volume = order_depth.buy_orders[best_bid]

        # Only trade if momentum is strong enough
        if momentum > momentum_threshold:
            # Expecting price to go up — buy
            if best_ask <= vwap_now - take_threshold and position < position_limit:
                qty = min(position_limit - position, buy_volume)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))

        elif momentum < -momentum_threshold:
            # Expecting price to go down — sell
            if best_bid >= vwap_now + take_threshold and position > -position_limit:
                qty = min(position_limit + position, sell_volume)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))

        return orders

    def fixed_resin_strategy(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        position_limit: int,
        fair_value: int = 10000,
        base_width: int = 2,
    ) -> List[Order]:
        orders = []
        self.resin_tick += 1

        # Widen spread after halfway
        width = base_width + (self.resin_tick // 1500)
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())

        buy_volume = -order_depth.sell_orders[best_ask]
        sell_volume = order_depth.buy_orders[best_bid]

        # Take liquidity
        if best_ask <= fair_value - width and position < position_limit:
            qty = min(position_limit - position, buy_volume)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if best_bid >= fair_value + width and position > -position_limit:
            qty = min(position_limit + position, sell_volume)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        # Post liquidity slightly outside spread
        bbbf = max([p for p in order_depth.buy_orders if p <
                   fair_value - width], default=fair_value - width - 1)
        baaf = min([p for p in order_depth.sell_orders if p >
                   fair_value + width], default=fair_value + width + 1)

        post_buy_qty = position_limit - position
        if post_buy_qty > 0:
            orders.append(Order(product, bbbf + 1, post_buy_qty))

        post_sell_qty = position_limit + position
        if post_sell_qty > 0:
            orders.append(Order(product, baaf - 1, -post_sell_qty))

        return orders

    def run(self, state: TradingState):
        result = {}

        if "RAINFOREST_RESIN" in state.order_depths:
            position = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.fixed_resin_strategy(
                product="RAINFOREST_RESIN",
                order_depth=state.order_depths["RAINFOREST_RESIN"],
                position=position,
                position_limit=50,
                fair_value=10000,
                base_width=2
            )

        if "KELP" in state.order_depths:
            position = state.position.get("KELP", 0)
            result["KELP"] = self.kelp_momentum_strategy(
                product="KELP",
                order_depth=state.order_depths["KELP"],
                position=position,
                position_limit=50,
                window=6,
                take_threshold=1.5,
                momentum_threshold=0.3
            )

        trader_data = {
            "kelp_vwap": self.kelp_vwap_history
        }
        return result, 1, jsonpickle.encode(trader_data)
