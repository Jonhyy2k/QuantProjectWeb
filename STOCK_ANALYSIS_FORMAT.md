# STOCK_ANALYSIS_RESULTS.txt Format Specification

This document defines the expected format for stock analysis results to ensure compatibility with the QuantPulse dashboard.

## File Structure

The file should contain multiple analysis blocks separated by a specific delimiter:

```
===== STOCK_ANALYSIS_RESULTS =====
Generated on: YYYY-MM-DD HH:MM:SS
=== ANALYSIS FOR {SYMBOL} ===
... analysis content ...
================================

===== STOCK_ANALYSIS_RESULTS =====
Generated on: YYYY-MM-DD HH:MM:SS
=== ANALYSIS FOR {SYMBOL} ===
... analysis content ...
================================
```

## Required Fields

Each analysis block must contain the following fields:

1. **Header**:
   ```
   ===== STOCK_ANALYSIS_RESULTS =====
   Generated on: YYYY-MM-DD HH:MM:SS
   === ANALYSIS FOR {SYMBOL} ===
   ```

2. **Basic Information**:
   ```
   Company: {Company Name}             // Optional but recommended
   Industry: {Industry Name}           // Optional
   Sector: {Sector Name}               // Optional
   Current Price: ${PRICE}             // REQUIRED (with or without $ symbol)
   Change: {CHANGE_VALUE} ({CHANGE_PERCENT}%)  // Optional but recommended
   Sigma Score: {SIGMA_VALUE}          // REQUIRED
   Recommendation: {RECOMMENDATION}    // REQUIRED
   ```

3. **Price Predictions Section**:
   ```
   === PRICE PREDICTIONS ===
   30-Day Target: ${TARGET_PRICE_30D} ({RETURN_30D}%)
   60-Day Target: ${TARGET_PRICE_60D} ({RETURN_60D}%)
   Prediction Plot: prediction_plots/{SYMBOL}_prediction_{DATE}_{TIME}.png
   ```

4. **Risk Metrics Section**:
   ```
   === RISK METRICS ===
   Maximum Drawdown: {DRAWDOWN_VALUE}%
   Sharpe Ratio: {SHARPE_VALUE}
   Kelly Criterion: {KELLY_VALUE}
   ```

5. **Footer Delimiter**:
   ```
   ================================
   ```

## Format Guidelines

1. All price values should be decimal numbers, with or without the dollar symbol
2. Percentage values should include the % symbol
3. Dates should be in the format YYYY-MM-DD
4. Times should be in the format HH:MM:SS
5. Section headers should be enclosed with triple equal signs on each side: `=== SECTION NAME ===`
6. The main delimiter between analyses should be a line with 32 equal signs: `================================`

## Example

Here's a correctly formatted example:

```
===== STOCK_ANALYSIS_RESULTS =====
Generated on: 2025-05-05 12:34:56
=== ANALYSIS FOR AAPL ===
Company: Apple Inc
Industry: Technology
Sector: Consumer Electronics
Current Price: $188.38
Change: -14.81 (-7.29%)
Sigma Score: 0.17560
Recommendation: STRONG SELL - Negative trend with limited reversal signals

=== PRICE PREDICTIONS ===
30-Day Target: $176.69 (-6.2%)
60-Day Target: $165.68 (-12.1%)
Prediction Plot: prediction_plots/AAPL_prediction_20250505_123456.png

=== RISK METRICS ===
Maximum Drawdown: -15.4%
Sharpe Ratio: 0.45
Kelly Criterion: 0.08
================================
```

## Backward Compatibility

The system will attempt to parse older formats that may not strictly adhere to this specification, but to ensure reliable functionality, please follow this format for all new analysis results.