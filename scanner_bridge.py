"""
Scanner Bridge
==============
Calls market-psar-scanner ONLY to detect sells for open positions.

We don't use the scanner for buy signals - those come from the HTML files.
The scanner is only used to check if any open positions have moved to Sell zone.
"""

import subprocess
import sys
import re
from pathlib import Path
from typing import List, Set
from config import SCANNER_DIR


class ScannerBridge:
    """Bridge to market-psar-scanner for sell detection"""
    
    def __init__(self):
        self.scanner_dir = SCANNER_DIR
        self._validated = False
    
    def _validate(self) -> bool:
        """Check if scanner is accessible"""
        if self._validated:
            return True
            
        main_py = self.scanner_dir / 'main.py'
        if not main_py.exists():
            print(f"⚠️  Scanner not found at: {self.scanner_dir}")
            print(f"   Set SCANNER_DIR environment variable")
            return False
        
        self._validated = True
        return True
    
    def find_sells(self, tickers: List[str]) -> Set[str]:
        """
        Check which tickers are currently in Sell zone.
        
        Calls market-psar-scanner with the specific tickers and
        parses output to find which are in Sell.
        
        Args:
            tickers: List of tickers to check
        
        Returns:
            Set of tickers currently in Sell zone
        """
        if not tickers:
            return set()
        
        if not self._validate():
            return set()
        
        # Write tickers to temp file
        temp_file = Path('/tmp/bt_check_sells.txt')
        
        try:
            # Write our tickers
            with open(temp_file, 'w') as f:
                f.write('\n'.join(tickers))
            
            # Run scanner with -mystocks and --tickers-file pointing to our temp file
            cmd = [sys.executable, 'main.py', '-mystocks', '--tickers-file', str(temp_file), '--no-email', '--quiet']
            
            print(f"   Running scanner on {len(tickers)} tickers...", end='', flush=True)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.scanner_dir),
                timeout=300  # 5 min timeout for large lists
            )
            
            print(" done.")
            
            output = result.stdout
            
            # Check for errors
            if result.returncode != 0 and result.stderr:
                print(f"⚠️  Scanner warning: {result.stderr[:200]}")
            
            # Parse output to find sells
            sells = self._parse_sells(output, set(tickers))
            return sells
            
        except subprocess.TimeoutExpired:
            print("\n⚠️  Scanner timed out (5 min)")
            return set()
        except Exception as e:
            print(f"\n⚠️  Scanner error: {e}")
            return set()
        finally:
            # Clean up temp file
            temp_file.unlink(missing_ok=True)
    
    def _parse_sells(self, output: str, known_tickers: Set[str]) -> Set[str]:
        """Parse scanner output to find tickers in Sell zone"""
        sells = set()
        
        in_sell_section = False
        
        for line in output.split('\n'):
            line_upper = line.upper()
            
            # Detect sell section
            if '🔴' in line or 'SELL' in line_upper:
                if 'SECTION' in line_upper or 'ZONE' in line_upper or line.strip().startswith('🔴'):
                    in_sell_section = True
                    continue
            
            # Detect section change (exit sell section)
            if in_sell_section:
                if any(marker in line for marker in ['🟢', '⚡', '💰', '⏸️', '===', '---']):
                    if 'SELL' not in line_upper:
                        in_sell_section = False
                        continue
            
            # Extract tickers from sell section
            if in_sell_section:
                # Find potential tickers
                words = re.findall(r'\b([A-Z]{1,5})\b', line)
                for word in words:
                    if word in known_tickers:
                        sells.add(word)
        
        # Also check for explicit sell markers anywhere
        for ticker in known_tickers:
            # Look for patterns like "AAPL ... SELL" or "🔴 AAPL"
            patterns = [
                rf'\b{ticker}\b.*(?:SELL|🔴)',
                rf'(?:SELL|🔴).*\b{ticker}\b',
            ]
            for pattern in patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    sells.add(ticker)
        
        return sells
    
    def check_single_ticker(self, ticker: str) -> str:
        """
        Check current zone for a single ticker.
        Returns: 'strong_buy', 'buy', 'early_buy', 'hold', 'sell', or 'unknown'
        """
        if not self._validate():
            return 'unknown'
        
        try:
            # Quick check using scanner
            result = subprocess.run(
                [sys.executable, 'main.py', '--no-email', '--quiet', '--tickers', ticker],
                capture_output=True,
                text=True,
                cwd=str(self.scanner_dir),
                timeout=60
            )
            
            output = result.stdout.upper()
            
            if 'STRONG BUY' in output and ticker.upper() in output:
                return 'strong_buy'
            elif 'EARLY BUY' in output and ticker.upper() in output:
                return 'early_buy'
            elif 'SELL' in output and ticker.upper() in output:
                return 'sell'
            elif 'HOLD' in output and ticker.upper() in output:
                return 'hold'
            elif 'BUY' in output and ticker.upper() in output:
                return 'buy'
            
            return 'unknown'
            
        except Exception as e:
            return 'unknown'


# Simple sell detection without scanner (fallback)
def detect_sells_from_file(content: str, tickers: List[str]) -> Set[str]:
    """
    Parse a scanner output file to find which tickers are in Sell zone.
    Used when we have a new file and want to find sells.
    """
    sells = set()
    tickers_set = set(t.upper() for t in tickers)
    
    in_sell_section = False
    
    for line in content.split('\n'):
        line_upper = line.upper()
        
        # Detect sell section
        if 'SELL' in line_upper and ('🔴' in line or 'SECTION' in line_upper or 'ZONE' in line_upper):
            in_sell_section = True
            continue
        
        # Exit sell section on other section headers
        if in_sell_section and any(x in line for x in ['🟢', '⚡', '💰', '⏸️']):
            in_sell_section = False
            continue
        
        if in_sell_section:
            words = re.findall(r'\b([A-Z]{1,5})\b', line)
            for word in words:
                if word in tickers_set:
                    sells.add(word)
    
    return sells


if __name__ == '__main__':
    bridge = ScannerBridge()
    print(f"Scanner directory: {bridge.scanner_dir}")
    print(f"Scanner available: {bridge._validate()}")
