from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle


class Trader:
    def __init__(self):
        self.kelp_vwap = []
        self.tick = 0

    def resin_strategy(
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

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            if best_ask <= fair_value - width:
                quantity = min(-order_depth.sell_orders[best_ask],
                               position_limit - position)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            if best_bid >= fair_value + width:
                quantity = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity

        baaf = min([p for p in order_depth.sell_orders if p >
                   fair_value + width], default=fair_value + width + 1)
        bbbf = max([p for p in order_depth.buy_orders if p <
                   fair_value - width], default=fair_value - width - 1)

        buy_quantity = position_limit - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, bbbf + 1, buy_quantity))

        sell_quantity = position_limit + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    def kelp_strategy(
        self,
        product: str,
        order_depth: OrderDepth,
        timespan: int,
        position: int,
        position_limit: int,
        take_spread: float = 3.0,
        min_edge: float = 2.0
    ) -> List[Order]:
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            ask_volume = -order_depth.sell_orders[best_ask]
            bid_volume = order_depth.buy_orders[best_bid]
            total_volume = ask_volume + bid_volume

            current_vwap = int(
                (best_bid * ask_volume + best_ask * bid_volume) / total_volume
            ) if total_volume > 0 else (best_ask + best_bid) // 2

            # === Bootstrap VWAP if needed ===
            if len(self.kelp_vwap) == 0:
                self.kelp_vwap.append(
                    {"vwap": current_vwap, "vol": total_volume})

            self.kelp_vwap.append({"vwap": current_vwap, "vol": total_volume})
            if len(self.kelp_vwap) > timespan:
                self.kelp_vwap.pop(0)

            weighted_vwap = sum(x["vwap"] * x["vol"] for x in self.kelp_vwap)
            total_vol = sum(x["vol"] for x in self.kelp_vwap)
            fair_value = int(
                weighted_vwap / total_vol) if total_vol > 0 else current_vwap

            spread = best_ask - best_bid

            # Simple trend filter
            trend = self.kelp_vwap[-1]["vwap"] - self.kelp_vwap[0]["vwap"]

            # === Take aggressive trades only if the edge is good ===
            if spread >= take_spread:
                # BUY if price is lower than fair and trend is up
                if best_ask <= fair_value - min_edge and trend >= 0:
                    quantity = min(ask_volume, position_limit - position)
                    if quantity > 0:
                        orders.append(Order(product, best_ask, quantity))

                # SELL if price is higher than fair and trend is down
                if best_bid >= fair_value + min_edge and trend <= 0:
                    quantity = min(bid_volume, position_limit + position)
                    if quantity > 0:
                        orders.append(Order(product, best_bid, -quantity))

            # Passive orders for recovery
            baaf = min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2)

            buy_quantity = position_limit - position
            if buy_quantity > 0:
                orders.append(Order(product, bbbf + 1, buy_quantity))

            sell_quantity = position_limit + position
            if sell_quantity > 0:
                orders.append(Order(product, baaf - 1, -sell_quantity))

        return orders

    def run(self, state: TradingState):
        result = {}
        self.tick += 1

        if "RAINFOREST_RESIN" in state.order_depths:
            position = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.resin_strategy(
                product="RAINFOREST_RESIN",
                order_depth=state.order_depths["RAINFOREST_RESIN"],
                fair_value=10000,
                width=2,
                position=position,
                position_limit=50
            )

        if "KELP" in state.order_depths:
            position = state.position.get("KELP", 0)
            result["KELP"] = self.kelp_strategy(
                product="KELP",
                order_depth=state.order_depths["KELP"],
                timespan=12,
                position=position,
                position_limit=50,
                take_spread=3.0,
                min_edge=2.0
            )

        trader_data = {"kelp_vwap": self.kelp_vwap}
        return result, 1, jsonpickle.encode(trader_data)
