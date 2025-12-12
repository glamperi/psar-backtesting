"""
Price Fetcher
=============
Fetches stock prices with market-aware timing logic.

Entry price rules:
- Pre-market (before 9:30 AM ET): Use previous day's close
- Intraday (9:30 AM - 4:00 PM ET): Use today's open
- After hours (after 4:00 PM ET): Use today's close
- Weekend: Use Friday's close

For closing positions (sells), always use current/latest price.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import get_market_status


class PriceFetcher:
    """Fetches stock prices with market-aware timing"""
    
    def __init__(self):
        self._cache = {}  # Simple cache for current session
    
    def get_entry_prices(self, tickers: List[str]) -> Dict[str, dict]:
        """
        Get entry prices for tickers based on current market status.
        
        Returns dict of ticker -> {price, price_type, date, time}
        """
        if not tickers:
            return {}
        
        market = get_market_status()
        results = {}
        
        # Fetch historical data to get open/close prices
        try:
            # Get 5 days of data to handle weekends
            data = yf.download(
                tickers, 
                period='5d',
                progress=False,
                group_by='ticker' if len(tickers) > 1 else None
            )
            
            if data.empty:
                return results
            
            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        ticker_data = data
                    else:
                        ticker_data = data[ticker]
                    
                    if ticker_data.empty:
                        continue
                    
                    # Get the appropriate price based on market status
                    if market['price_type'] == 'open':
                        # Intraday: use today's open
                        price = float(ticker_data['Open'].iloc[-1])
                        price_date = ticker_data.index[-1]
                    elif market['price_type'] == 'close':
                        # After hours: use today's close
                        price = float(ticker_data['Close'].iloc[-1])
                        price_date = ticker_data.index[-1]
                    else:
                        # Pre-market or weekend: use previous close
                        price = float(ticker_data['Close'].iloc[-1])
                        price_date = ticker_data.index[-1]
                    
                    results[ticker] = {
                        'price': price,
                        'price_type': market['price_type'],
                        'date': price_date.strftime('%Y-%m-%d') if hasattr(price_date, 'strftime') else str(price_date)[:10],
                        'fetched_at': datetime.now().isoformat(),
                        'market_status': market['description']
                    }
                    
                except Exception as e:
                    print(f"Warning: Could not get price for {ticker}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Warning: Price fetch error: {e}")
        
        return results
    
    def get_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """
        Get current/latest prices for tickers.
        Used for closing positions and P/L calculations.
        """
        if not tickers:
            return {}
        
        prices = {}
        
        try:
            if len(tickers) == 1:
                stock = yf.Ticker(tickers[0])
                hist = stock.history(period='1d')
                if not hist.empty:
                    prices[tickers[0]] = float(hist['Close'].iloc[-1])
            else:
                data = yf.download(tickers, period='1d', progress=False)
                if not data.empty:
                    for ticker in tickers:
                        try:
                            if ticker in data['Close'].columns:
                                price = data['Close'][ticker].iloc[-1]
                                if not pd.isna(price):
                                    prices[ticker] = float(price)
                            elif len(tickers) == 1:
                                prices[ticker] = float(data['Close'].iloc[-1])
                        except:
                            pass
        except Exception as e:
            print(f"Warning: Current price fetch error: {e}")
            # Fall back to individual fetches
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period='1d')
                    if not hist.empty:
                        prices[ticker] = float(hist['Close'].iloc[-1])
                except:
                    pass
        
        return prices
    
    def get_intraday_quotes(self, tickers: List[str]) -> Dict[str, dict]:
        """
        Get real-time intraday quotes with bid/ask if available.
        """
        if not tickers:
            return {}
        
        quotes = {}
        
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                quotes[ticker] = {
                    'price': info.get('regularMarketPrice') or info.get('currentPrice'),
                    'open': info.get('regularMarketOpen'),
                    'high': info.get('regularMarketDayHigh'),
                    'low': info.get('regularMarketDayLow'),
                    'previous_close': info.get('regularMarketPreviousClose'),
                    'change_pct': info.get('regularMarketChangePercent'),
                    'volume': info.get('regularMarketVolume'),
                }
            except Exception as e:
                # Fall back to history
                try:
                    hist = stock.history(period='1d')
                    if not hist.empty:
                        quotes[ticker] = {
                            'price': float(hist['Close'].iloc[-1]),
                            'open': float(hist['Open'].iloc[-1]),
                            'high': float(hist['High'].iloc[-1]),
                            'low': float(hist['Low'].iloc[-1]),
                        }
                except:
                    pass
        
        return quotes


# Module-level instance for convenience
_fetcher = None

def get_fetcher() -> PriceFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = PriceFetcher()
    return _fetcher


if __name__ == '__main__':
    # Test
    from config import get_market_status
    
    market = get_market_status()
    print(f"Market status: {market}")
    
    fetcher = PriceFetcher()
    
    test_tickers = ['AAPL', 'MSFT', 'NVDA']
    print(f"\nEntry prices for {test_tickers}:")
    
    prices = fetcher.get_entry_prices(test_tickers)
    for ticker, data in prices.items():
        print(f"  {ticker}: ${data['price']:.2f} ({data['price_type']} on {data['date']})")
