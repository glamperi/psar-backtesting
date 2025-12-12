"""
File Parser
===========
Parses scanner output (HTML or text) to extract categorized stock lists.

Supports V2 scanner output format with sections:
- 🟢🟢 STRONG BUY
- 🟢 BUY  
- ⚡ EARLY BUY
- 💰 DIVIDEND
- ⏸️ HOLD
- 🔴 SELL
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup


def parse_file(filepath: str) -> Dict[str, List[str]]:
    """
    Parse a scanner output file and extract categorized stocks.
    
    Args:
        filepath: Path to HTML or text file
    
    Returns:
        Dict with keys: strong_buys, buys, early_buys, dividends, holds, sells
    """
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    
    return parse_content(content)


def parse_content(content: str) -> Dict[str, List[str]]:
    """
    Parse scanner output content (HTML or text).
    
    Returns:
        Dict with keys: strong_buys, buys, early_buys, dividends, holds, sells
    """
    # Check if HTML
    if '<html' in content.lower() or '<table' in content.lower():
        return _parse_html(content)
    else:
        return _parse_text(content)


def _parse_html(content: str) -> Dict[str, List[str]]:
    """Parse HTML scanner output"""
    soup = BeautifulSoup(content, 'html.parser')
    
    result = {
        'strong_buys': [],
        'buys': [],
        'early_buys': [],
        'dividends': [],
        'holds': [],
        'sells': []
    }
    
    # Map CSS classes to categories (V2 scanner format)
    # Header rows use classes like 'th-strongbuy', 'th-earlybuy', etc.
    css_class_map = {
        'th-strongbuy': 'strong_buys',
        'th-earlybuy': 'early_buys',
        'th-buy': 'buys',
        'th-dividend': 'dividends',
        'th-hold': 'holds',
        'th-sell': 'sells',
        'section-strongbuy': 'strong_buys',
        'section-earlybuy': 'early_buys',
        'section-buy': 'buys',
        'section-dividend': 'dividends',
        'section-hold': 'holds',
        'section-sell': 'sells',
    }
    
    current_section = None
    
    # Find all table rows
    for tr in soup.find_all('tr'):
        tr_classes = tr.get('class', [])
        
        # Check if this is a section header row
        for css_class in tr_classes:
            if css_class in css_class_map:
                current_section = css_class_map[css_class]
                continue
        
        # If we're in a section, extract ticker from first cell
        if current_section:
            cells = tr.find_all('td')
            if cells:
                first_cell = cells[0]
                # Ticker is usually in <strong> tag or just text
                strong = first_cell.find('strong')
                if strong:
                    ticker = _extract_ticker(strong.get_text().strip())
                else:
                    ticker = _extract_ticker(first_cell.get_text().strip())
                
                if ticker and ticker not in result[current_section]:
                    # Skip common header words
                    if ticker not in ['TICKER', 'SYMBOL', 'STOCK', 'NAME', 'PRICE']:
                        result[current_section].append(ticker)
    
    # Also check for section divs with text (backup method)
    for div in soup.find_all('div'):
        div_classes = div.get('class', [])
        text = div.get_text().upper()
        
        for css_class in div_classes:
            if css_class in css_class_map:
                # Found a section header div, look for table after it
                table = div.find_next('table')
                if table:
                    section = css_class_map[css_class]
                    for tr in table.find_all('tr'):
                        cells = tr.find_all('td')
                        if cells:
                            strong = cells[0].find('strong')
                            if strong:
                                ticker = _extract_ticker(strong.get_text().strip())
                            else:
                                ticker = _extract_ticker(cells[0].get_text().strip())
                            
                            if ticker and ticker not in result[section]:
                                if ticker not in ['TICKER', 'SYMBOL', 'STOCK', 'NAME', 'PRICE']:
                                    result[section].append(ticker)
    
    return result


def _parse_text(content: str) -> Dict[str, List[str]]:
    """Parse plain text scanner output"""
    result = {
        'strong_buys': [],
        'buys': [],
        'early_buys': [],
        'dividends': [],
        'holds': [],
        'sells': []
    }
    
    # Common words to exclude
    excluded = {
        'BUY', 'SELL', 'HOLD', 'STRONG', 'EARLY', 'DIVIDEND', 'TIER', 'TOP',
        'PSAR', 'RSI', 'OBV', 'DMI', 'ADX', 'MACD', 'PRSI', 'ATR', 'SBI',
        'THE', 'AND', 'FOR', 'WITH', 'FROM', 'INTO', 'ZONE', 'SIGNAL',
        'PRICE', 'DAYS', 'STOCKS', 'MODE', 'MARKET', 'SCAN', 'REPORT',
        'SECTION', 'CONFIRMED', 'FRESH', 'SIGNALS', 'POSITIONS',
        'TICKER', 'YIELD', 'OPEN', 'CLOSE', 'HIGH', 'LOW', 'VOLUME',
        'PRIMARY', 'LOGIC', 'TREND', 'SCORE', 'ALIGNMENT', 'ACCUMULATION',
        'BUYS', 'SELLS', 'HOLDS', 'FILTER', 'FILTERS', 'SCANNED', 'ANALYZED',
        'TRUE', 'FALSE', 'NULL', 'NONE', 'CLASS', 'STYLE', 'DIV', 'TABLE',
        'COLOR', 'WHITE', 'GREEN', 'RED', 'BLUE', 'BACKGROUND', 'PADDING',
        'MARGIN', 'FONT', 'SIZE', 'WEIGHT', 'BOLD', 'BORDER', 'LEFT'
    }
    
    current_section = None
    
    for line in content.split('\n'):
        line_text = line.strip()
        line_upper = line_text.upper()
        
        # Detect section headers (check for CSS class names too)
        if 'STRONG' in line_upper and 'BUY' in line_upper:
            current_section = 'strong_buys'
            continue
        elif 'EARLY' in line_upper and 'BUY' in line_upper:
            current_section = 'early_buys'
            continue
        elif 'SECTION-EARLYBUY' in line_upper or 'TH-EARLYBUY' in line_upper:
            current_section = 'early_buys'
            continue
        elif 'SECTION-STRONGBUY' in line_upper or 'TH-STRONGBUY' in line_upper:
            current_section = 'strong_buys'
            continue
        elif 'DIVIDEND' in line_upper or '💰' in line_text:
            current_section = 'dividends'
            continue
        elif 'SECTION-HOLD' in line_upper or ('HOLD' in line_upper and '⏸️' in line_text):
            current_section = 'holds'
            continue
        elif 'SECTION-SELL' in line_upper or ('SELL' in line_upper and 'STRONG' not in line_upper):
            if 'SECTION' in line_upper or '🔴' in line_text or line_text.startswith('SELL'):
                current_section = 'sells'
                continue
        elif 'BUY' in line_upper and 'STRONG' not in line_upper and 'EARLY' not in line_upper:
            if current_section not in ['strong_buys', 'early_buys']:
                current_section = 'buys'
                continue
        
        # Skip header/separator lines
        if line_text.startswith('=') or line_text.startswith('-'):
            continue
        if not line_text:
            continue
        
        # Extract tickers from current section
        if current_section:
            # Look for ticker patterns
            # Tickers are typically 1-5 uppercase letters
            words = re.findall(r'[⭐]?\b([A-Z]{1,5})\b', line_upper)
            
            for word in words:
                if word not in excluded and len(word) >= 2:
                    if word not in result[current_section]:
                        result[current_section].append(word)
    
    return result


def _extract_ticker(text: str) -> Optional[str]:
    """Extract ticker symbol from text (handles emoji stars, etc)"""
    # Remove common non-ticker characters
    cleaned = re.sub(r'[⭐★☆\s]', '', text)
    
    # Extract uppercase letters
    match = re.match(r'^([A-Z]{1,5})(?:\s|$|[^A-Z])', cleaned.upper())
    if match:
        ticker = match.group(1)
        # Validate it's not a common word
        if ticker not in {'THE', 'AND', 'FOR', 'BUY', 'SELL'}:
            return ticker
    
    return None


def get_all_tickers(parsed: Dict[str, List[str]]) -> List[str]:
    """Get all unique tickers from parsed result"""
    all_tickers = set()
    for category in parsed.values():
        all_tickers.update(category)
    return list(all_tickers)


def get_buy_tickers(parsed: Dict[str, List[str]], mode: str = 'all') -> List[str]:
    """
    Get buy tickers filtered by mode.
    
    Args:
        parsed: Parsed stock categories
        mode: 'strong', 'early', 'all', or 'dividend'
    
    Returns:
        List of tickers
    """
    tickers = []
    
    if mode in ['strong', 'all']:
        tickers.extend(parsed.get('strong_buys', []))
    
    if mode in ['early', 'all']:
        tickers.extend(parsed.get('early_buys', []))
    
    if mode == 'all':
        tickers.extend(parsed.get('buys', []))
    
    if mode == 'dividend':
        tickers.extend(parsed.get('dividends', []))
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    
    return unique


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        result = parse_file(filepath)
        
        print(f"Parsed {filepath}:")
        for category, tickers in result.items():
            if tickers:
                print(f"  {category}: {len(tickers)} - {', '.join(tickers[:10])}")
                if len(tickers) > 10:
                    print(f"    ... and {len(tickers) - 10} more")
    else:
        print("Usage: python file_parser.py <scanner_output_file>")
