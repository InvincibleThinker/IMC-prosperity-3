from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order
import math

SUBMISSION = "SUBMISSION"
RAINFOREST_RESIN = "RAINFOREST_RESIN"
KELP = "KELP"

PRODUCTS = [RAINFOREST_RESIN, KELP]

DEFAULT_PRICES = {
    RAINFOREST_RESIN: 10_000,
    KELP: 10_000,
}


class Trader:

    def __init__(self) -> None:
        print("Initializing Trader...")

        self.position_limit = {
            RAINFOREST_RESIN: 50,
            KELP: 50,
        }

        self.round = 0
        self.cash = 0
        self.past_prices = {product: [] for product in PRODUCTS}
        self.ema_prices = {
            product: DEFAULT_PRICES[product] for product in PRODUCTS}
        self.ema_param = 0.5

    def get_position(self, product: str, state: TradingState) -> int:
        return state.position.get(product, 0)

    def get_mid_price(self, product: str, state: TradingState) -> float:
        default_price = self.ema_prices[product]
        order_depth = state.order_depths.get(product, None)

        if not order_depth:
            return default_price

        best_bid = max(
            order_depth.buy_orders) if order_depth.buy_orders else default_price
        best_ask = min(
            order_depth.sell_orders) if order_depth.sell_orders else default_price
        return (best_bid + best_ask) / 2

    def update_ema_prices(self, state: TradingState) -> None:
        for product in PRODUCTS:
            mid_price = self.get_mid_price(product, state)
            self.ema_prices[product] = (self.ema_param * mid_price
                                        + (1 - self.ema_param) * self.ema_prices[product])

    def resin_strategy(self, state: TradingState) -> List[Order]:
        position = self.get_position(RAINFOREST_RESIN, state)
        bid_volume = self.position_limit[RAINFOREST_RESIN] - position
        ask_volume = -self.position_limit[RAINFOREST_RESIN] - position

        return [
            Order(RAINFOREST_RESIN,
                  DEFAULT_PRICES[RAINFOREST_RESIN] - 1, bid_volume),
            Order(RAINFOREST_RESIN,
                  DEFAULT_PRICES[RAINFOREST_RESIN] + 1, ask_volume)
        ]

    def kelp_strategy(self, state: TradingState) -> List[Order]:
        position = self.get_position(KELP, state)
        current_ema = self.ema_prices[KELP]
        orders = []

        bid_volume = self.position_limit[KELP] - position
        ask_volume = -self.position_limit[KELP] - position

        if position == 0:
            orders.append(Order(KELP, math.floor(current_ema - 1), bid_volume))
            orders.append(Order(KELP, math.ceil(current_ema + 1), ask_volume))
        elif position > 0:
            orders.append(Order(KELP, math.floor(current_ema - 2), bid_volume))
            orders.append(Order(KELP, math.ceil(current_ema), ask_volume))
        else:
            orders.append(Order(KELP, math.floor(current_ema), bid_volume))
            orders.append(Order(KELP, math.ceil(current_ema + 2), ask_volume))

        return orders

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        self.round += 1
        self.update_ema_prices(state)

        result = {}

        try:
            result[RAINFOREST_RESIN] = self.resin_strategy(state)
        except Exception as e:
            print(f"Error in RAINFOREST_RESIN strategy: {e}")

        try:
            result[KELP] = self.kelp_strategy(state)
        except Exception as e:
            print(f"Error in KELP strategy: {e}")

        print(f"Round {self.round} completed")
        print(f"Current EMA prices: {self.ema_prices}")

        return result, 0, ""
