import json
import statistics
from datamodel import Order, OrderDepth, TradingState, ProsperityEncoder, Symbol
from typing import List, Dict, Tuple, Any


# ========== LOGGER ==========
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: Dict[Symbol, List[Order]], conversions: int, trader_data: str) -> None:
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
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: Dict[Symbol, Any]) -> list[list[Any]]:
        return [[listing.symbol, listing.product, listing.denomination] for listing in listings.values()]

    def compress_order_depths(self, order_depths: Dict[Symbol, OrderDepth]) -> Dict[Symbol, list[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}

    def compress_trades(self, trades: Dict[Symbol, List[Any]]) -> list[list[Any]]:
        return [
            [t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
            for trade_list in trades.values()
            for t in trade_list
        ]

    def compress_observations(self, obs: Any) -> list[Any]:
        return [
            obs.plainValueObservations,
            {
                k: [
                    v.bidPrice,
                    v.askPrice,
                    v.transportFees,
                    v.exportTariff,
                    v.importTariff,
                    v.sugarPrice,
                    v.sunlightIndex,
                ]
                for k, v in obs.conversionObservations.items()
            },
        ]

    def compress_orders(self, orders: Dict[Symbol, List[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for order_list in orders.values() for o in order_list]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value if len(value) <= max_length else value[: max_length - 3] + "..."


logger = Logger()


# ========== TRADER STRATEGY ==========
class Trader:
    def __init__(self):
        self.kelp_vwap = []
        self.kelp_prices = []
        self.tick = 0

    def resin_strategy(self, product, order_depth, fair_value, width, position, position_limit) -> List[Order]:
        orders = []
        buy_volume = sell_volume = 0

        logger.print(
            f"[Resin] Tick {self.tick} - Starting strategy for {product}")
        logger.print(f"[Resin] Position: {position}, Fair value: {fair_value}")

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask <= fair_value - width:
                qty = min(-order_depth.sell_orders[best_ask],
                          position_limit - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_volume += qty
                    logger.print(f"[Resin] Buying {qty} at {best_ask}")

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid >= fair_value + width:
                qty = min(
                    order_depth.buy_orders[best_bid], position_limit + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_volume += qty
                    logger.print(f"[Resin] Selling {qty} at {best_bid}")

        baaf = min([p for p in order_depth.sell_orders if p >
                   fair_value + width], default=fair_value + width + 1)
        bbbf = max([p for p in order_depth.buy_orders if p <
                   fair_value - width], default=fair_value - width - 1)

        buy_qty = position_limit - (position + buy_volume)
        if buy_qty > 0:
            orders.append(Order(product, bbbf + 1, buy_qty))
            logger.print(f"[Resin] Passive buy {buy_qty} at {bbbf + 1}")

        sell_qty = position_limit + (position - sell_volume)
        if sell_qty > 0:
            orders.append(Order(product, baaf - 1, -sell_qty))
            logger.print(f"[Resin] Passive sell {sell_qty} at {baaf - 1}")

        return orders

    def kelp_strategy(self, product, order_depth, position, position_limit) -> List[Order]:
        orders = []
        logger.print(
            f"[Kelp] Tick {self.tick} - Starting strategy for {product}")
        logger.print(f"[Kelp] Position: {position}")

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            ask_vol = -order_depth.sell_orders[best_ask]
            bid_vol = order_depth.buy_orders[best_bid]
            total_vol = ask_vol + bid_vol

            mid_price = (best_ask + best_bid) / 2
            self.kelp_prices.append(mid_price)
            if len(self.kelp_prices) > 40:
                self.kelp_prices.pop(0)

            vwap_window = 8 if statistics.stdev(
                self.kelp_prices[-20:]) > 4 else 16
            current_vwap = (best_bid * ask_vol + best_ask *
                            bid_vol) // total_vol if total_vol else int(mid_price)
            self.kelp_vwap.append(
                {"vwap": int(current_vwap), "vol": int(total_vol)})
            if len(self.kelp_vwap) > vwap_window:
                self.kelp_vwap.pop(0)

            total_weighted = sum(x["vwap"] * x["vol"] for x in self.kelp_vwap)
            total_vol = sum(x["vol"] for x in self.kelp_vwap)
            fair_value = total_weighted // total_vol if total_vol else int(
                mid_price)

            logger.print(
                f"[Kelp] Fair value: {fair_value}, Spread: {best_ask - best_bid}")

            spread = best_ask - best_bid
            min_edge = max(1, int(spread * 0.3))
            take_spread = max(2, int(spread * 0.6))

            if spread >= take_spread:
                edge = fair_value - best_ask
                if edge >= min_edge:
                    qty = min(ask_vol, position_limit - position)
                    if edge > 3:
                        qty = int(qty * 1.5)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))
                        logger.print(
                            f"[Kelp] Taking ask {qty} at {best_ask}, edge: {edge}")

                edge = best_bid - fair_value
                if edge >= min_edge:
                    qty = min(bid_vol, position_limit + position)
                    if edge > 3:
                        qty = int(qty * 1.5)
                    if qty > 0:
                        orders.append(Order(product, best_bid, -qty))
                        logger.print(
                            f"[Kelp] Hitting bid {qty} at {best_bid}, edge: {edge}")

            baaf = min([p for p in order_depth.sell_orders if p >
                       fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p <
                       fair_value - 1], default=fair_value - 2)

            buy_qty = position_limit - position
            sell_qty = position_limit + position

            if buy_qty > 0:
                orders.append(Order(product, bbbf + 1, buy_qty))
                logger.print(f"[Kelp] Passive buy {buy_qty} at {bbbf + 1}")
            if sell_qty > 0:
                orders.append(Order(product, baaf - 1, -sell_qty))
                logger.print(f"[Kelp] Passive sell {sell_qty} at {baaf - 1}")

        return orders

    def run(self, state: TradingState) -> Tuple[Dict[Symbol, List[Order]], int, str]:
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
                position=pos,
                position_limit=50
            )

        # ✅ Safe serialization of trader data
        trader_data = {"kelp_vwap": self.kelp_vwap}
        trader_data_str = json.dumps(trader_data, cls=ProsperityEncoder)

        logger.flush(state, result, conversions=1, trader_data=trader_data_str)
        return result, 1, trader_data_str
