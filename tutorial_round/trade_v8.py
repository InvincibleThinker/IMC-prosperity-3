from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle


class Trader:
    def __init__(self):
        # RAINFOREST_RESIN parameters
        self.rainforest_prices = []
        self.rainforest_window = 20
        self.base_fair_value = 10000

        # KELP parameters
        self.kelp_prices = []
        self.kelp_ewma = None
        self.ewma_alpha = 0.2  # Weight for recent prices
        self.kelp_window = 15

    def calculate_mid_price(self, order_depth: OrderDepth) -> float:
        """Calculate current mid price from best bid/ask"""
        best_ask = min(order_depth.sell_orders.keys()
                       ) if order_depth.sell_orders else None
        best_bid = max(order_depth.buy_orders.keys()
                       ) if order_depth.buy_orders else None

        if best_ask and best_bid:
            return (best_ask + best_bid) / 2
        return None

    # ========== RAINFOREST_RESIN - Dynamic Fair Value Strategy ==========
    def handle_rainforest(self, order_depth: OrderDepth, position: int, position_limit: int) -> List[Order]:
        orders = []
        current_mid = self.calculate_mid_price(order_depth)
        if current_mid is None:
            return orders

        # Update price history
        self.rainforest_prices.append(current_mid)
        if len(self.rainforest_prices) > self.rainforest_window:
            self.rainforest_prices.pop(0)

        # Calculate dynamic parameters
        if len(self.rainforest_prices) >= 5:
            short_ma = sum(self.rainforest_prices[-5:])/5
            volatility = max(
                self.rainforest_prices[-5:]) - min(self.rainforest_prices[-5:])
            # Blend with base value
            fair_value = int((short_ma + self.base_fair_value) / 2)
            spread_width = max(2, int(volatility * 0.6))
        else:
            fair_value = self.base_fair_value
            spread_width = 2

        # Liquidity taking
        best_ask = min(order_depth.sell_orders.keys())
        if best_ask < fair_value - spread_width//2:
            ask_vol = -order_depth.sell_orders[best_ask]
            buy_qty = min(ask_vol, position_limit - position)
            if buy_qty > 0:
                orders.append(Order("RAINFOREST_RESIN", best_ask, buy_qty))

        best_bid = max(order_depth.buy_orders.keys())
        if best_bid > fair_value + spread_width//2:
            bid_vol = order_depth.buy_orders[best_bid]
            sell_qty = min(bid_vol, position_limit + position)
            if sell_qty > 0:
                orders.append(Order("RAINFOREST_RESIN", best_bid, -sell_qty))

        # Liquidity providing with adaptive spread
        buy_price = int(fair_value - spread_width)
        sell_price = int(fair_value + spread_width)

        remaining_buy = position_limit - position - \
            sum(o.quantity for o in orders if o.quantity > 0)
        if remaining_buy > 0:
            orders.append(Order("RAINFOREST_RESIN", buy_price, remaining_buy))

        remaining_sell = position_limit + position - \
            sum(abs(o.quantity) for o in orders if o.quantity < 0)
        if remaining_sell > 0:
            orders.append(Order("RAINFOREST_RESIN",
                          sell_price, -remaining_sell))

        return orders

    # ========== KELP - EWMA Mean Reversion Strategy ==========
    def handle_kelp(self, order_depth: OrderDepth, position: int, position_limit: int) -> List[Order]:
        orders = []
        current_mid = self.calculate_mid_price(order_depth)
        if current_mid is None:
            return orders

        # Update price history and calculate EWMA
        self.kelp_prices.append(current_mid)
        if len(self.kelp_prices) > self.kelp_window:
            self.kelp_prices.pop(0)

        # Initialize or update EWMA
        if self.kelp_ewma is None:
            self.kelp_ewma = current_mid
        else:
            self.kelp_ewma = self.ewma_alpha * current_mid + \
                (1 - self.ewma_alpha) * self.kelp_ewma

        # Calculate dynamic threshold
        price_window = self.kelp_prices[-10:] if len(
            self.kelp_prices) >= 10 else self.kelp_prices
        volatility = max(price_window) - \
            min(price_window) if price_window else 3.0
        threshold = 0.8 * volatility  # Aggressive threshold

        # Trading logic
        best_ask = min(order_depth.sell_orders.keys(), default=None)
        best_bid = max(order_depth.buy_orders.keys(), default=None)

        # Buy signal
        if best_ask and current_mid < (self.kelp_ewma - threshold):
            max_buy = position_limit - position
            ask_vol = -order_depth.sell_orders[best_ask]
            buy_qty = min(ask_vol, max_buy)
            if buy_qty > 0:
                orders.append(Order("KELP", best_ask, buy_qty))

        # Sell signal
        if best_bid and current_mid > (self.kelp_ewma + threshold):
            max_sell = position_limit + position
            bid_vol = order_depth.buy_orders[best_bid]
            sell_qty = min(bid_vol, max_sell)
            if sell_qty > 0:
                orders.append(Order("KELP", best_bid, -sell_qty))

        # Passive orders beyond threshold
        passive_buy_price = int(self.kelp_ewma - threshold * 1.5)
        passive_sell_price = int(self.kelp_ewma + threshold * 1.5)

        remaining_buy = position_limit - position - \
            sum(o.quantity for o in orders if o.quantity > 0)
        if remaining_buy > 0:
            orders.append(Order("KELP", passive_buy_price, remaining_buy))

        remaining_sell = position_limit + position - \
            sum(abs(o.quantity) for o in orders if o.quantity < 0)
        if remaining_sell > 0:
            orders.append(Order("KELP", passive_sell_price, -remaining_sell))

        return orders

    def run(self, state: TradingState):
        result = {}

        # Process RAINFOREST_RESIN
        if "RAINFOREST_RESIN" in state.order_depths:
            position = state.position.get("RAINFOREST_RESIN", 0)
            result["RAINFOREST_RESIN"] = self.handle_rainforest(
                state.order_depths["RAINFOREST_RESIN"],
                position,
                50  # Position limit
            )

        # Process KELP
        if "KELP" in state.order_depths:
            position = state.position.get("KELP", 0)
            result["KELP"] = self.handle_kelp(
                state.order_depths["KELP"],
                position,
                50  # Position limit
            )

        # Serialize custom data
        trader_data = {
            "rainforest_prices": self.rainforest_prices,
            "kelp_prices": self.kelp_prices,
            "kelp_ewma": self.kelp_ewma
        }
        return result, 1, jsonpickle.encode(trader_data)
