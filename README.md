# 🧠 IMC Prosperity Challenge — Final Trading Bot (Improved Edition)

This repository contains the **final improved version** of my trading bot for the IMC Prosperity 3 Algorithmic Trading Challenge.  
After the official competition ended, I continued working on optimizing and modularizing the strategy logic to better reflect my learning journey and demonstrate my algorithmic trading capabilities.

---

## 🚀 Challenge Summary

🌟 **Grateful and excited to share my journey through the IMC Prosperity Challenge!** 🌟  
Coming in as a **solo participant among 12,600+ teams**, here’s what I achieved:

- 📈 **256th Rank in India**  
- 🌍 **1413th Rank Globally**

---

## 📚 What I Learned

- 📘 Core trading models like:
  - Black-Scholes Option Pricing
  - Statistical Arbitrage
  - Mean Reversion
  - Pair Trading

- 📊 Adapted strategies dynamically based on volatility regimes  
- 💪 Resilience: After a tough Round 4, I bounced back strong in Round 5!

This challenge has been an invaluable stepping stone in my journey into **quantitative finance** — and it's just the beginning!  
I'm excited to keep exploring the world of **algorithmic and quantitative trading**. 🌐

---

## 📦 Strategy Overview (by Asset)

| Asset                    | Strategy                       | Description                                                                 |
|--------------------------|--------------------------------|-----------------------------------------------------------------------------|
| `KELP`                   | Bollinger Band Mean Reversion | Volatility-adaptive thresholds for long/short entries                      |
| `VOLCANIC_ROCK`          | Mean Reversion                | Rolling Bollinger bands + historical price memory                          |
| `VOLCANIC_ROCK_VOUCHERS`| Options Mean Reversion        | ITM option strategies mirroring underlying; 10500 strike special logic     |
| `SQUID_INK`              | Extreme Move Detection        | Reacts to sharp price deviations using recent volatility                   |
| `RAINFOREST_RESIN`       | Market Making & Taking        | Competitive quoting around fair value walls                                |
| `PICNIC_BASKETS`         | ETF Arbitrage                 | Basket vs. component mispricing arbitrage                                  |
| `DJEMBES`                | Mean Reversion & Spread Adj.  | Basic momentum and spread management                                       |
| `CROISSANTS`             | Informed Trader Tracking      | Track Olivia's trades — best Sharpe trader in simulations                  |
| `MAGNIFICENT_MACARONS`   | Sunlight-Driven Momentum      | Trend-based trading based on sunlight index & TP/SL levels                 |

---

## 🛠 Technologies Used

- Python 3  
- `numpy`, `pandas`, `matplotlib`, `optuna`, `scikit-learn`, `jsonpickle`  

---

## 📁 Files

- [`improved_trading_bot.py`](./improved_trading_bot.py) — final submission-ready version
- `README.md` — this file

---

## 🧠 Author & Future Plans

Hi! I'm an aspiring **quantitative trader** passionate about blending **data science** and **financial intuition**. This bot reflects my iterative learning process during and **after** the IMC challenge. I plan to expand this further with:

- Backtesting integrations
- Live market simulations
- Sharpe/PNL dashboards

Feel free to connect or explore further!  
📬 [LinkedIn](#) | 🌐 [Website/Portfolio](#)

---
# IMC-prosperity-3
