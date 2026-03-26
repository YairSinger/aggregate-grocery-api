# Data Acquisition

This project collects grocery price data from major Israeli supermarket chains as mandated by the **Israeli Price Transparency Law (2014)**.

## Current Implementation

The data is currently fetched using a **Targeted Bulk Scraper** found in `app/pipeline/modiin_bulk_fetcher.py`.

### How it works:
1. **Store Identification**: We target specific branch IDs for the Modi'in area to minimize data usage (stays under 500MB, well within the 10GB limit).
   - **Shufersal**: 119 (Deal Center), 134 (Yishpro), 489 (Express).
   - **Rami Levy**: 101 (Yishpro), 102 (Shilat).
   - **Victory**: 201 (Modi'in Center).
2. **Session Handling**: 
   - For **Cerberus portals** (Rami Levy, Victory, Yohananof), we perform a "silent login" to obtain session cookies (`cftpSID`) and bypass basic bot detection.
   - For **Shufersal**, we use **Playwright** to handle the AJAX-driven dropdowns and table generation.
3. **Data Processing**: 
   - Files are downloaded as `.xml.gz`.
   - `parser.py` extracts items and prices using memory-efficient streaming.
   - `processor.py` calculates the effective price (merging prices with promotions) and normalizes units (e.g., converting grams to kg).

## Areas for Improvement

While the current targeted approach works for Modi'in, the following improvements should be considered:

1. **Leverage Existing Solutions**: Future iterations should investigate and potentially integrate logic from established community projects:
   - [OpenIsraeliSupermarkets/israeli-supermarket-scarpers](https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-scarpers) - Most comprehensive unified scraper.
   - [fluhus/prices](https://github.com/fluhus/prices) - Excellent reference for URL patterns and parsing.
   - [AKorets/israeli-supermarket-data](https://github.com/AKorets/israeli-supermarket-data) - Good for unified CSV/Pandas exports.
   - [yonicd/supermarketprices](https://github.com/yonicd/supermarketprices) - Shows efficient enumeration techniques.
2. **Bot Detection Bypassing**: The supermarket portals frequently update their anti-bot measures. Moving towards a more robust "stealth" browser setup or using resident proxies may be necessary for high-frequency updates.
3. **Product Matching (Aggregators)**: The biggest challenge remains matching the same product across different chains (e.g., identifying that "Tnuva Milk 1L" has different codes in Shufersal vs. Rami Levy). This is handled via the `Aggregate` system in this project but can be improved using NLP or barcode-matching services like Pricez.

## Running the Pipeline

To refresh the Modi'in data:
```bash
export PYTHONPATH=$PYTHONPATH:.
python3 app/pipeline/modiin_bulk_fetcher.py
python3 app/pipeline/modiin_scraper.py
```
