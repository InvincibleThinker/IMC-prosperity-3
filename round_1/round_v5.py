from datamodel import Order
import statistics


class Trader:
    def __init__(self):
        self.position = {"KELP": 0, "RAINFOREST_RESIN": 0, "SQUID_INK": 0}
        self.price_data = {"KELP": [], "RAINFOREST_RESIN": [], "SQUID_INK": []}
        self.position_limit = 50

    def run(self, state, logger):
        result = {}
        trader_data = {}
        observations = {}
        conversions = {}

        for product in state.order_depths:
            orders = []
            order_depth = state.order_depths[product]
            position = self.position[product]
            limit = self.position_limit

            best_ask = min(order_depth.sell_orders.keys()
                           ) if order_depth.sell_orders else None
            best_bid = max(order_depth.buy_orders.keys()
                           ) if order_depth.buy_orders else None
            ask_vol = abs(order_depth.sell_orders[best_ask]) if best_ask else 0
            bid_vol = abs(order_depth.buy_orders[best_bid]) if best_bid else 0

            # Mid price for fair value tracking
            if best_ask and best_bid:
                mid_price = (best_ask + best_bid) / 2
            elif best_ask:
                mid_price = best_ask
            elif best_bid:
                mid_price = best_bid
            else:
                continue

            # Update price history
            self.price_data[product].append(mid_price)
            if len(self.price_data[product]) > 50:
                self.price_data[product].pop(0)
            prices = self.price_data[product]

            # === STRATEGY LOGIC PER PRODUCT ===

            # ----- KELP: VWAP-based strategy -----
            if product == "KELP":
                if len(prices) < 20:
                    continue
                fair_value = int(statistics.mean(prices[-20:]))
                volatility = statistics.stdev(
                    prices[-5:]) if len(prices) >= 5 else 1
                spread = best_ask - best_bid if best_ask and best_bid else 0

                if spread < 2 or volatility < 0.5:
                    continue

                min_edge = max(1, int(spread * 0.3))
                take_spread = max(2, int(spread * 0.6))
                max_exposure = int(limit * 0.6)

                if spread >= take_spread:
                    if fair_value - best_ask >= min_edge and position < max_exposure:
                        qty = min(ask_vol, limit - position)
                        orders.append(Order(product, best_ask, qty))
                        logger.print(
                            f"[KELP] BUY {qty} @ {best_ask} | FV={fair_value} | Pos={position}")

                    if best_bid - fair_value >= min_edge and position > -max_exposure:
                        qty = min(bid_vol, position + limit)
                        orders.append(Order(product, best_bid, -qty))
                        logger.print(
                            f"[KELP] SELL {qty} @ {best_bid} | FV={fair_value} | Pos={position}")

            # ----- RAINFOREST_RESIN: mean-reversion -----
            elif product == "RAINFOREST_RESIN":
                fair_value = int(statistics.mean(
                    prices[-15:])) if len(prices) >= 15 else mid_price
                buy_threshold = fair_value - 2
                sell_threshold = fair_value + 2

                if best_ask and best_ask < buy_threshold and position < limit:
                    qty = min(ask_vol, limit - position)
                    orders.append(Order(product, best_ask, qty))
                    logger.print(
                        f"[RESIN] BUY {qty} @ {best_ask} | FV={fair_value} | Pos={position}")

                if best_bid and best_bid > sell_threshold and position > -limit:
                    qty = min(bid_vol, position + limit)
                    orders.append(Order(product, best_bid, -qty))
                    logger.print(
                        f"[RESIN] SELL {qty} @ {best_bid} | FV={fair_value} | Pos={position}")

            # ----- SQUID_INK: conservative threshold strategy -----
            elif product == "SQUID_INK":
                if len(prices) < 20:
                    continue
                fair_value = int(statistics.mean(prices[-20:]))
                buy_threshold = fair_value - 4
                sell_threshold = fair_value + 4

                max_exposure = int(limit * 0.5)

                if best_ask and best_ask < buy_threshold and position < max_exposure:
                    qty = min(ask_vol, limit - position)
                    orders.append(Order(product, best_ask, qty))
                    logger.print(
                        f"[SQUID] BUY {qty} @ {best_ask} | FV={fair_value} | Pos={position}")

                if best_bid and best_bid > sell_threshold and position > -max_exposure:
                    qty = min(bid_vol, position + limit)
                    orders.append(Order(product, best_bid, -qty))
                    logger.print(
                        f"[SQUID] SELL {qty} @ {best_bid} | FV={fair_value} | Pos={position}")

            result[product] = orders

        return result, conversions, trader_data
