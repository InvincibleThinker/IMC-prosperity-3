import json
import statistics
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


# ========== LOGGER FOR JMERELE VISUALIZER ==========
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects, sep=" ", end="\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict, conversions: int, trader_data: str) -> None:
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
        print(self.to_json([
            self.compress_state(state, self.truncate(
                state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str):
        return [
            state.timestamp,
            trader_data,
            [[l.symbol, l.product, l.denomination]
                for l in state.listings.values()],
            {s: [od.buy_orders, od.sell_orders]
                for s, od in state.order_depths.items()},
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for trades in state.own_trades.values() for t in trades],
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for trades in state.market_trades.values() for t in trades],
            state.position,
            [
                state.observations.plainValueObservations,
                {p: [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex]
                 for p, o in state.observations.conversionObservations.items()}
            ]
        ]

    def compress_orders(self, orders: dict):
        return [[o.symbol, o.price, o.quantity] for order_list in orders.values() for o in order_list]

    def to_json(self, value) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value if len(value) <= max_length else value[: max_length - 3] + "..."


logger = Logger()


# ========== STRATEGY ==========
class Trader:
    def __init__(self):
        self.kelp_vwap = []
        self.kelp_prices = []
        self.squid_prices = []

    def resin_strategy(self, order_depth, fair_value, width, position, position_limit):
        orders = []
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask <= fair_value - width:
                qty = min(-order_depth.sell_orders[best_ask],
                          position_limit - position)
                if qty > 0:
                    orders.append(Order("RAINFOREST_RESIN", best_ask, qty))

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid >= fair_value + width:
                qty = min(
                    order_depth.buy_orders[best_bid], position + position_limit)
                if qty > 0:
                    orders.append(Order("RAINFOREST_RESIN", best_bid, -qty))

        return orders

    def kelp_strategy(self, order_depth, position, position_limit):
        orders = []
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            mid_price = (best_ask + best_bid) / 2
            self.kelp_prices.append(mid_price)

            if len(self.kelp_prices) > 40:
                self.kelp_prices.pop(0)

            volatility = statistics.stdev(
                self.kelp_prices[-20:]) if len(self.kelp_prices) >= 20 else 0
            vwap_window = 8 if volatility > 4 else 16

            ask_vol = -order_depth.sell_orders[best_ask]
            bid_vol = order_depth.buy_orders[best_bid]
            total_vol = ask_vol + bid_vol
            current_vwap = int((best_bid * ask_vol + best_ask *
                               bid_vol) / total_vol) if total_vol else int(mid_price)

            self.kelp_vwap.append({"vwap": current_vwap, "vol": total_vol})
            if len(self.kelp_vwap) > vwap_window:
                self.kelp_vwap.pop(0)

            total_weighted = sum(x["vwap"] * x["vol"] for x in self.kelp_vwap)
            total_vol = sum(x["vol"] for x in self.kelp_vwap)
            fair_value = int(total_weighted /
                             total_vol) if total_vol else int(mid_price)

            spread = best_ask - best_bid
            min_edge = max(1, int(spread * 0.3))
            take_spread = max(2, int(spread * 0.6))

            if spread >= take_spread:
                if fair_value - best_ask >= min_edge:
                    qty = min(ask_vol, position_limit - position)
                    if qty > 0:
                        orders.append(Order("KELP", best_ask, qty))
                if best_bid - fair_value >= min_edge:
                    qty = min(bid_vol, position + position_limit)
                    if qty > 0:
                        orders.append(Order("KELP", best_bid, -qty))

        return orders

    def squid_strategy(self, order_depth, position, position_limit):
        orders = []
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            mid_price = (best_ask + best_bid) / 2
            self.squid_prices.append(mid_price)

            if len(self.squid_prices) > 50:
                self.squid_prices.pop(0)

            if len(self.squid_prices) >= 10:
                mean = statistics.mean(self.squid_prices)
                stdev = statistics.stdev(self.squid_prices)
                upper_band = mean + 1.3 * stdev
                lower_band = mean - 1.3 * stdev

                if best_ask < lower_band:
                    qty = min(-order_depth.sell_orders[best_ask],
                              position_limit - position)
                    if qty > 0:
                        orders.append(Order("SQUID_INK", best_ask, qty))
                if best_bid > upper_band:
                    qty = min(
                        order_depth.buy_orders[best_bid], position + position_limit)
                    if qty > 0:
                        orders.append(Order("SQUID_INK", best_bid, -qty))

        return orders

    def run(self, state: TradingState):
        orders = {}
        conversions = 0
        trader_data = ""

        if "RAINFOREST_RESIN" in state.order_depths:
            pos = state.position.get("RAINFOREST_RESIN", 0)
            orders["RAINFOREST_RESIN"] = self.resin_strategy(
                state.order_depths["RAINFOREST_RESIN"], fair_value=10000, width=1.8,
                position=pos, position_limit=50
            )

        if "KELP" in state.order_depths:
            pos = state.position.get("KELP", 0)
            orders["KELP"] = self.kelp_strategy(
                state.order_depths["KELP"], position=pos, position_limit=50
            )

        if "SQUID_INK" in state.order_depths:
            pos = state.position.get("SQUID_INK", 0)
            orders["SQUID_INK"] = self.squid_strategy(
                state.order_depths["SQUID_INK"], position=pos, position_limit=50
            )

        trader_data = json.dumps({
            "kelp_vwap": self.kelp_vwap,
            "kelp_prices": self.kelp_prices,
            "squid_prices": self.squid_prices
        })

        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
