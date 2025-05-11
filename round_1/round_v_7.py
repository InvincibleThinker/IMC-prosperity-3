from datamodel import Order, OrderDepth, TradingState, Symbol
import json
import statistics
from typing import Any


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json([
                self.compress_state(state, ""),
                self.compress_orders(orders),
                conversions,
                "",
                "",
            ])
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json([
                self.compress_state(state, self.truncate(
                    state.traderData, max_item_length)),
                self.compress_orders(orders),
                conversions,
                self.truncate(trader_data, max_item_length),
                self.truncate(self.logs, max_item_length),
            ])
        )
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            [[listing.symbol, listing.product, listing.denomination]
             for listing in state.listings.values()],
            {symbol: [depth.buy_orders, depth.sell_orders]
             for symbol, depth in state.order_depths.items()},
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for trades in state.own_trades.values() for t in trades],
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for trades in state.market_trades.values() for t in trades],
            state.position,
            [state.observations.plainValueObservations, {
                k: [v.bidPrice, v.askPrice, v.transportFees, v.exportTariff,
                    v.importTariff, v.sugarPrice, v.sunlightIndex]
                for k, v in state.observations.conversionObservations.items()
            }],
        ]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for ol in orders.values() for o in ol]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value if len(value) <= max_length else value[: max_length - 3] + "..."


logger = Logger()


class Trader:
    def __init__(self):
        self.history = {"KELP": [], "SQUID_INK": []}
        self.maxlen = 50
        self.tick = 0

    def pendulum_strategy(self, product, order_depth, position, limit):
        orders = []
        history = self.history[product]

        if order_depth.buy_orders and order_depth.sell_orders:
            best_bid = max(order_depth.buy_orders)
            best_ask = min(order_depth.sell_orders)
            mid_price = (best_bid + best_ask) / 2
            history.append(mid_price)
            if len(history) > self.maxlen:
                history.pop(0)

            momentum = 0
            if len(history) >= 3:
                momentum = history[-1] - history[-3]

            price_std = statistics.stdev(
                history[-10:]) if len(history) >= 10 else 1
            edge = max(1, int(price_std * 0.8))

            fair = sum(history) / len(history)
            buy_qty = max(0, limit - position)
            sell_qty = max(0, position + limit)

            if momentum < -1 and best_ask < fair - edge and buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
            elif momentum > 1 and best_bid > fair + edge and sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

            passive_buy_price = best_bid - 1
            passive_sell_price = best_ask + 1

            if buy_qty > 0:
                orders.append(Order(product, passive_buy_price, buy_qty // 2))
            if sell_qty > 0:
                orders.append(
                    Order(product, passive_sell_price, -sell_qty // 2))

        return orders

    def resin_strategy(self, order_depth, fair_value, width, position, position_limit):
        orders = []
        buy_qty = max(0, position_limit - position)
        sell_qty = max(0, position + position_limit)

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask <= fair_value - width and buy_qty > 0:
                orders.append(Order("RAINFOREST_RESIN", best_ask,
                                    min(-order_depth.sell_orders[best_ask], buy_qty)))

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid >= fair_value + width and sell_qty > 0:
                orders.append(Order("RAINFOREST_RESIN", best_bid,
                                    -min(order_depth.buy_orders[best_bid], sell_qty)))
        return orders

    def run(self, state: TradingState):
        result = {}
        self.tick += 1

        kelp_pos = state.position.get("KELP", 0)
        squid_pos = state.position.get("SQUID_INK", 0)
        resin_pos = state.position.get("RAINFOREST_RESIN", 0)

        if "KELP" in state.order_depths:
            result["KELP"] = self.pendulum_strategy(
                "KELP", state.order_depths["KELP"], kelp_pos, 50)

        if "SQUID_INK" in state.order_depths:
            result["SQUID_INK"] = self.pendulum_strategy(
                "SQUID_INK", state.order_depths["SQUID_INK"], squid_pos, 50)

        if "RAINFOREST_RESIN" in state.order_depths:
            result["RAINFOREST_RESIN"] = self.resin_strategy(
                state.order_depths["RAINFOREST_RESIN"], 10000, 1.8, resin_pos, 50)

        logger.flush(state, result, 1, "")
        return result, 1, ""
