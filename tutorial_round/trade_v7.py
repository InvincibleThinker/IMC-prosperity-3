from typing import Dict, List, Tuple
from datamodel import OrderDepth, TradingState, Order
import math
import numpy as np

SUBMISSION = "SUBMISSION"
RAINFOREST_RESIN = "RAINFOREST_RESIN"
KELP = "KELP"

PRODUCTS = [RAINFOREST_RESIN, KELP]

DEFAULT_PRICES = {
    RAINFOREST_RESIN: 10_000,
    KELP: 2_028,
}


class Trader:
    def __init__(self) -> None:
        print("Initializing Trader...")
        self.position_limit = {
            RAINFOREST_RESIN: 50,
            KELP: 50,
        }
        self.round = 0

        # Price tracking
        self.price_history = {product: [] for product in PRODUCTS}
        self.ema_prices = DEFAULT_PRICES.copy()
        self.volatility = {product: 0 for product in PRODUCTS}

        # KELP Strategy Parameters
        self.kelp_spread_multiplier = 1.5
        self.kelp_trend_window = 20
        self.kelp_order_book_ratio_threshold = 1.5
        self.kelp_max_risk = 0.4  # 40% of position limit

        # Resin Strategy Parameters
        self.base_spread = 1
        self.volatility_window = 20
        self.spread_multiplier = 2.0

        # Risk Management
        self.stop_loss_pct = 0.03  # 3% stop-loss
        self.trailing_take_profit = 0.02  # 2% trailing profit

    def get_position(self, product: str, state: TradingState) -> int:
        return state.position.get(product, 0)

    def get_mid_price(self, product: str, state: TradingState) -> float:
        order_depth = state.order_depths.get(product, None)
        if not order_depth:
            return self.ema_prices[product]

        best_bid = max(
            order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(
            order_depth.sell_orders) if order_depth.sell_orders else None

        if best_bid and best_ask:
            return (best_bid + best_ask) / 2
        return self.ema_prices[product]

    def calculate_volatility(self, product: str) -> float:
        if len(self.price_history[product]) < 2:
            return 0
        returns = np.diff(np.log(self.price_history[product]))
        return np.std(returns) * math.sqrt(252)  # Annualized volatility

    def update_price_history(self, state: TradingState):
        for product in PRODUCTS:
            mid_price = self.get_mid_price(product, state)
            self.price_history[product].append(mid_price)

            # Keep volatility window size
            if len(self.price_history[product]) > self.volatility_window:
                self.price_history[product].pop(0)

            # Update volatility measure
            self.volatility[product] = self.calculate_volatility(product)

    def dynamic_spread(self, product: str) -> float:
        """Volatility-adjusted spread with minimum spread protection"""
        base = self.base_spread
        # Scale volatility
        volatility_adj = max(1, self.volatility[product] * 1000)
        spread = base + (volatility_adj * self.spread_multiplier)
        return max(2, min(spread, 10))  # Keep between 2-10

    # Enhanced KELP Strategy
    def kelp_strategy(self, state: TradingState) -> List[Order]:
        orders = []
        product = KELP
        position = self.get_position(product, state)
        mid_price = self.get_mid_price(product, state)

        # Order Book Analysis
        ob = state.order_depths.get(product, OrderDepth())
        buy_volume = sum(ob.buy_orders.values())
        sell_volume = sum(ob.sell_orders.values())
        # Prevent division by zero
        ob_ratio = buy_volume / (sell_volume + 1e-6)

        # Trend Detection (MACD-style)
        short_ema = np.mean(self.price_history[product][-5:]) if len(
            self.price_history[product]) >= 5 else mid_price
        long_ema = np.mean(self.price_history[product][-20:]) if len(
            self.price_history[product]) >= 20 else mid_price
        trend_strength = short_ema - long_ema

        # Momentum Indicator
        momentum = mid_price - \
            np.mean(self.price_history[product][-3:-1]
                    ) if len(self.price_history[product]) >= 3 else 0

        # Position Sizing
        max_position = int(self.position_limit[product] * self.kelp_max_risk)
        position_ratio = abs(position) / max_position

        # Trading Signals
        entry_conditions = [
            ob_ratio > self.kelp_order_book_ratio_threshold,
            trend_strength > 0,
            momentum > 0,
            position_ratio < 0.8
        ]

        exit_conditions = [
            ob_ratio < 1/self.kelp_order_book_ratio_threshold,
            trend_strength < 0,
            momentum < 0,
            position_ratio > 0.5
        ]

        # Dynamic Pricing
        spread = self.dynamic_spread(product) * self.kelp_spread_multiplier
        bid_price = math.floor(mid_price - spread/2)
        ask_price = math.ceil(mid_price + spread/2)

        # Order Logic
        if all(entry_conditions):
            volume = min(max_position - position, 3)  # Conservative entry
            orders.append(Order(product, bid_price, volume))
        elif any(exit_conditions):
            volume = max(-max_position - position, -
                         abs(position)//2)  # Partial exit
            orders.append(Order(product, ask_price, volume))
        else:
            # Market making with risk-adjusted spread
            # Widen spread as position increases
            mm_spread = spread * (1 + position_ratio)
            safe_bid = math.floor(mid_price - mm_spread/2)
            safe_ask = math.floor(mid_price + mm_spread/2)
            orders.append(Order(product, safe_bid, 1))
            orders.append(Order(product, safe_ask, -1))

        return orders

    # Improved Resin Strategy
    def resin_strategy(self, state: TradingState) -> List[Order]:
        product = RAINFOREST_RESIN
        position = self.get_position(product, state)
        mid_price = self.get_mid_price(product, state)

        # Dynamic Spread Calculation
        spread = self.dynamic_spread(product)
        target_price = self.ema_prices[product]

        # Trend Following Adjustment
        price_deviation = (mid_price - target_price) / target_price
        # Expand spread in volatile markets
        spread *= (1 + abs(price_deviation) * 2)

        # Order Placement
        bid_price = math.floor(target_price - spread/2)
        ask_price = math.ceil(target_price + spread/2)

        # Position-based Aggressiveness
        position_factor = 1 - (abs(position) / self.position_limit[product])
        bid_volume = int(
            (self.position_limit[product] - position) * position_factor)
        ask_volume = int(
            (-self.position_limit[product] - position) * position_factor)

        # Add orders
        return [
            Order(product, bid_price, max(1, bid_volume)),
            Order(product, ask_price, min(-1, ask_volume))
        ]

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        self.round += 1
        self.update_price_history(state)
        result = {product: [] for product in PRODUCTS}

        try:
            result[RAINFOREST_RESIN] = self.resin_strategy(state)
            result[KELP] = self.kelp_strategy(state)
        except Exception as e:
            print(f"Error in strategies: {e}")

        return result, 0, ""
