# AI-Enabled Foreign Trading System

A Flask academic prototype for browsing international products with prices converted into INR, content-based product recommendations, and rule-based transaction risk screening.

## Live currency conversion
- Product records store a local-currency amount and ISO currency code (for example, JPY, EUR, GBP, USD, CNY, CHF, KRW).
- The app fetches the latest available pair rate from Frankfurter API v2 (`/v2/rate/{BASE}/INR`) and calculates the INR display/checkout amount.
- Rates are cached in memory for one hour to reduce API calls. The rate's effective date and applied rate are shown on product pages.
- If the rate API is unavailable, the app does not create an order using an old or guessed conversion rate.
- Frankfurter rates are reference rates, not real-time bank/card/payment quotes. The API publishes rates according to its data providers' schedules; weekends/holidays may show the most recent working-day rate.

## Features
- User registration and login
- International product catalogue and search
- INR conversion using current available reference exchange rates
- TF-IDF + cosine-similarity product recommendations
- Rule-based fraud risk score and admin review
- Demo order history (no real payment or shipping)

## Run locally
1. Install Python 3.10+.
2. Open this folder in VS Code/PyCharm.
3. Run `pip install -r requirements.txt`.
4. Run `python app.py`.
5. Open `http://127.0.0.1:5000`.

The exchange-rate API requires an internet connection. No API key is needed.

## Important limitations
This is an academic prototype. It does not integrate a payment gateway, actual foreign merchant checkout, customs/tax calculation, or international logistics. The fraud detector is a transparent rule-based demo, not a trained ML model.

Exchange-rate source: https://frankfurter.dev/


## Expanded product catalogue and live search
The app now includes a larger international sample catalogue across multiple countries and currencies. Products are added to an existing SQLite database on startup without duplicating products already present. The home page search box displays matching product suggestions underneath as the user types; selecting a suggestion opens that product page. Search also matches country, category, description, and tags.
