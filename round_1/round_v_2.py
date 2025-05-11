import json
from typing import Any, Dict, List
import jsonpickle
import numpy as np
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


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

    def compress_state(self, state: TradingState, trader_data: str) -> List[Any]:
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

    def compress_listings(self, listings: Dict[Symbol, Listing]) -> List[List[Any]]:
        return [[listing.symbol, listing.product, listing.denomination] for listing in listings.values()]

    def compress_order_depths(self, order_depths: Dict[Symbol, OrderDepth]) -> Dict[Symbol, List[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}

    def compress_trades(self, trades: Dict[Symbol, List[Trade]]) -> List[List[Any]]:
        return [[trade.symbol, trade.price, trade.quantity, trade.buyer, trade.seller, trade.timestamp]
                for arr in trades.values() for trade in arr]

    def compress_observations(self, observations: Observation) -> List[Any]:
        return [observations.plainValueObservations, {
            product: [
                obs.bidPrice,
                obs.askPrice,
                obs.transportFees,
                obs.exportTariff,
                obs.importTariff,
                obs.sugarPrice,
                obs.sunlightIndex,
            ] for product, obs in observations.conversionObservations.items()
        }]

    def compress_orders(self, orders: Dict[Symbol, List[Order]]) -> List[List[Any]]:
        return [[order.symbol, order.price, order.quantity] for arr in orders.values() for order in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value[:max_length-3] + "..." if len(value) > max_length else value


logger = Logger()


class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    SQUID_INK = "SQUID_INK"


PARAMS = {
    Product.RAINFOREST_RESIN: {
        "fair_value": 10000,
        "take_width": 2,
        "spread": 3,
        "position_limit": 50
    },
    Product.KELP: {
        "take_width": 2,
        "min_edge": 1.5,
        "reversion_beta": -0.35,
        "window_size": 3,
        "position_limit": 50
    },
    Product.SQUID_INK: {
        "base_edge": 0.3,
        "min_edge": 0.2,
        "edge_decay": 0.9,
        "loss_threshold": -1500,
        "position_limit": 40,
        "risk_window": 200,
        "price_sensitivity": 0.1
    }
}


class Trader:
    def __init__(self):
        self.position_limits = {
            prod: params["position_limit"] for prod, params in PARAMS.items()}

    def run(self, state: TradingState) -> tuple[Dict[Symbol, List[Order]], int, str]:
        result = {}
        conversions = 0
        trader_data = {"squid_state": {}, "kelp_data": {}}

        if state.traderData:
            trader_data = jsonpickle.decode(state.traderData)
            logger.print("Loaded trader data:", trader_data)

        try:
            # Rainforest Resin Strategy
            if Product.RAINFOREST_RESIN in state.order_depths:
                result[Product.RAINFOREST_RESIN] = self.trade_resin(state)

            # Kelp Strategy
            if Product.KELP in state.order_depths:
                result[Product.KELP] = self.trade_kelp(state, trader_data)

            # Squid Ink Strategy
            if Product.SQUID_INK in state.order_depths:
                result[Product.SQUID_INK], trader_data = self.trade_squid(
                    state, trader_data)

        except Exception as e:
            logger.print("Error:", str(e))

        trader_data_str = jsonpickle.encode(trader_data)
        logger.flush(state, result, conversions, trader_data_str)
        return result, conversions, trader_data_str

    def trade_resin(self, state: TradingState) -> List[Order]:
        params = PARAMS[Product.RAINFOREST_RESIN]
        position = state.position.get(Product.RAINFOREST_RESIN, 0)
        orders = []

        order_depth = state.order_depths[Product.RAINFOREST_RESIN]
        best_bid = max(order_depth.buy_orders.keys(), default=0)
        best_ask = min(order_depth.sell_orders.keys(), default=0)

        for i in range(3):
            bid_price = params["fair_value"] - params["take_width"] - i
            ask_price = params["fair_value"] + params["take_width"] + i

            if bid_price > best_bid:
                quantity = min(10, params["position_limit"] - position)
                orders.append(
                    Order(Product.RAINFOREST_RESIN, bid_price, quantity))

            if ask_price < best_ask:
                quantity = min(10, params["position_limit"] + position)
                orders.append(
                    Order(Product.RAINFOREST_RESIN, ask_price, -quantity))

        return orders

    def trade_kelp(self, state: TradingState, trader_data: dict) -> List[Order]:
        params = PARAMS[Product.KELP]
        position = state.position.get(Product.KELP, 0)
        orders = []
        order_depth = state.order_depths[Product.KELP]

        if "price_history" not in trader_data["kelp_data"]:
            trader_data["kelp_data"]["price_history"] = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_ask + best_bid) / 2
            trader_data["kelp_data"]["price_history"].append(mid_price)

            if len(trader_data["kelp_data"]["price_history"]) > params["window_size"]:
                trader_data["kelp_data"]["price_history"].pop(0)

        if len(trader_data["kelp_data"]["price_history"]) >= 2:
            last_price = trader_data["kelp_data"]["price_history"][-2]
            current_price = trader_data["kelp_data"]["price_history"][-1]
            returns = (current_price - last_price) / last_price
            pred_returns = returns * params["reversion_beta"]
            fair_price = current_price + (current_price * pred_returns)

            spread = fair_price * 0.0005
            orders.append(Order(Product.KELP, int(fair_price - spread), 5))
            orders.append(Order(Product.KELP, int(fair_price + spread), -5))

        return orders

    def trade_squid(self, state: TradingState, trader_data: dict) -> tuple[List[Order], dict]:
        params = PARAMS[Product.SQUID_INK]
        position = state.position.get(Product.SQUID_INK, 0)
        orders = []
        order_depth = state.order_depths[Product.SQUID_INK]

        # Initialize squid state
        squid_state = trader_data.setdefault("squid_state", {
            "current_edge": params["base_edge"],
            "cumulative_pnl": 0,
            "last_trade": state.timestamp,
            "position_history": [],
            "price_history": []
        })

        # Update price history
        best_bid = max(order_depth.buy_orders.keys(), default=0)
        best_ask = min(order_depth.sell_orders.keys(), default=0)
        mid_price = (best_bid + best_ask) / \
            2 if best_bid and best_ask else 1850
        squid_state["price_history"].append(mid_price)

        # Calculate current PnL
        current_pnl = self.calculate_squid_pnl(position, order_depth)
        squid_state["cumulative_pnl"] += current_pnl
        logger.print(
            f"Squid PnL: {current_pnl:.2f} | Total: {squid_state['cumulative_pnl']:.2f}")

        # Risk management
        if squid_state["cumulative_pnl"] < params["loss_threshold"]:
            logger.print(
                f"Squid halted: Cumulative PnL {squid_state['cumulative_pnl']:.2f}")
            return [], trader_data

        # Calculate adaptive edge
        edge = self.calculate_adaptive_edge(squid_state, mid_price, params)

        # Calculate aggressive prices
        bid_price = round(
            best_bid * (1 + params["price_sensitivity"]) - edge, 1)
        ask_price = round(
            best_ask * (1 - params["price_sensitivity"]) + edge, 1)

        # Place orders
        bid_qty = min(8, params["position_limit"] - position)
        ask_qty = min(8, params["position_limit"] + position)

        orders.append(Order(Product.SQUID_INK, bid_price, bid_qty))
        orders.append(Order(Product.SQUID_INK, ask_price, -ask_qty))

        # Position rotation
        if position != 0 and (state.timestamp - squid_state["last_trade"]) > params["risk_window"]:
            close_price = best_bid if position > 0 else best_ask
            orders.append(Order(Product.SQUID_INK, close_price, -position))
            logger.print(
                f"Position rotation: Closed {position} @ {close_price}")

        # Update state
        squid_state.update({
            "last_trade": state.timestamp,
            "current_edge": edge,
            "position_history": squid_state["position_history"][-9:] + [position]
        })

        return orders, trader_data

    def calculate_adaptive_edge(self, state: dict, mid_price: float, params: dict) -> float:
        """Dynamic edge calculation based on market volatility and position history"""
        price_history = state["price_history"][-5:] + [mid_price]
        volatility = np.std(price_history) if len(price_history) > 1 else 1.0

        position_history = state["position_history"]
        avg_position = np.mean(position_history) if position_history else 0
        position_factor = 1 - abs(avg_position)/params["position_limit"]

        return max(params["min_edge"],
                   params["base_edge"] * position_factor / max(volatility, 0.5))

    def calculate_squid_pnl(self, position: int, order_depth: OrderDepth) -> float:
        """Mark-to-market PnL calculation"""
        if position == 0:
            return 0

        best_bid = max(order_depth.buy_orders.keys(), default=0)
        best_ask = min(order_depth.sell_orders.keys(), default=0)
        if best_bid == 0 or best_ask == 0:
            return 0

        mid_price = (best_bid + best_ask) / 2
        return position * (mid_price - self.get_average_cost(position, order_depth))

    def get_average_cost(self, position: int, order_depth: OrderDepth) -> float:
        """Calculate average cost basis for current position"""
        # This is simplified - would need actual trade history for accurate calculation
        best_bid = max(order_depth.buy_orders.keys(), default=0)
        best_ask = min(order_depth.sell_orders.keys(), default=0)
        return (best_bid + best_ask) / 2
