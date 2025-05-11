import json
import statistics
from typing import Any

from datamodel import Order, OrderDepth, TradingState, Symbol, ProsperityEncoder


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(
                        state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            [[listing.symbol, listing.product, listing.denomination]
                for listing in state.listings.values()],
            {
                symbol: [depth.buy_orders, depth.sell_orders]
                for symbol, depth in state.order_depths.items()
            },
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for trades in state.own_trades.values() for t in trades],
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for trades in state.market_trades.values() for t in trades],
            state.position,
            [state.observations.plainValueObservations, {
                k: [
                    v.bidPrice, v.askPrice, v.transportFees,
                    v.exportTariff, v.importTariff, v.sugarPrice, v.sunlightIndex
                ] for k, v in state.observations.conversionObservations.items()
            }],
        ]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for ol in orders.values() for o in ol]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value if len(value) <= max_length else value[: max_length - 3] + "..."


logger = Logger()


class Trader:
    def __init__(self):
        self.price_data = {"KELP": [], "SQUID_INK": []}
        self.vwap_data = {"KELP": [], "SQUID_INK": []}
        self.tick = 0

    def vwap_strategy(self, product, order_depth, position, position_limit):
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            ask_vol = -order_depth.sell_orders[best_ask]
            bid_vol = order_depth.buy_orders[best_bid]
            mid_price = (best_ask + best_bid) / 2

            self.price_data[product].append(mid_price)
            if len(self.price_data[product]) > 40:
                self.price_data[product].pop(0)

            volatility = statistics.stdev(
                self.price_data[product][-20:]) if len(self.price_data[product]) >= 20 else 0
            vwap_window = 8 if volatility > 4 else 16

            total_vol = ask_vol + bid_vol
            current_vwap = (best_bid * ask_vol + best_ask *
                            bid_vol) // total_vol if total_vol else int(mid_price)
            self.vwap_data[product].append(
                {"vwap": current_vwap, "vol": total_vol})
            if len(self.vwap_data[product]) > vwap_window:
                self.vwap_data[product].pop(0)

            total_weighted = sum(x["vwap"] * x["vol"]
                                 for x in self.vwap_data[product])
            total_vol = sum(x["vol"] for x in self.vwap_data[product])
            fair_value = total_weighted // total_vol if total_vol else int(
                mid_price)

            spread = best_ask - best_bid
            min_edge = max(1, int(spread * 0.3))
            take_spread = max(2, int(spread * 0.6))

            # Avoid negative positions
            buy_qty = max(0, min(ask_vol, position_limit - position))
            sell_qty = max(0, min(bid_vol, position + position_limit))

            if spread >= take_spread:
                if fair_value - best_ask >= min_edge and buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                if best_bid - fair_value >= min_edge and sell_qty > 0:
                    orders.append(Order(product, best_bid, -sell_qty))

            baaf = min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2)

            passive_buy_qty = max(0, position_limit - position)
            passive_sell_qty = max(0, position + position_limit)

            if passive_buy_qty > 0:
                orders.append(Order(product, bbbf + 1, passive_buy_qty))
            if passive_sell_qty > 0:
                orders.append(Order(product, baaf - 1, -passive_sell_qty))

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
                orders.append(Order("RAINFOREST_RESIN", best_bid, -
                              min(order_depth.buy_orders[best_bid], sell_qty)))

        return orders

    def run(self, state: TradingState):
        result = {}
        self.tick += 1

        if "KELP" in state.order_depths:
            pos = max(0, state.position.get("KELP", 0))
            result["KELP"] = self.vwap_strategy(
                "KELP", state.order_depths["KELP"], pos, 50)

        if "SQUID_INK" in state.order_depths:
            pos = max(0, state.position.get("SQUID_INK", 0))
            result["SQUID_INK"] = self.vwap_strategy(
                "SQUID_INK", state.order_depths["SQUID_INK"], pos, 50)

        if "RAINFOREST_RESIN" in state.order_depths:
            pos = max(0, state.position.get("RAINFOREST_RESIN", 0))
            result["RAINFOREST_RESIN"] = self.resin_strategy(
                state.order_depths["RAINFOREST_RESIN"], 10000, 1.8, pos, 50
            )

        logger.flush(state, result, 1, "")
        return result, 1, ""
