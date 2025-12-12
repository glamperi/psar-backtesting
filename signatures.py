"""
Signature Manager
=================
Manages run signatures with file-based identification.

Key concept: Each unique file content gets ONE signature.
- Same file processed twice = same signature, uses stored data
- Signature stores all positions with entry prices from first run
- P/L updates as positions are closed (sells detected)

Signature data structure:
{
    "signature_id": "20251212_163045_a1b2c3",
    "file_hash": "sha256:abc123...",
    "created_at": "2025-12-12T16:30:45",
    "mode": "strong",
    "market_status": "After hours - using today close",
    "positions": {
        "AAPL": {
            "category": "strong_buy",
            "entry_price": 248.50,
            "entry_date": "2025-12-12",
            "entry_type": "close",
            "status": "open",  # or "closed"
            "exit_price": null,
            "exit_date": null,
            "exit_reason": null,
            "pnl_pct": null,
            "pnl_amt": null
        }
    },
    "summary": {
        "total_positions": 15,
        "open_positions": 12,
        "closed_positions": 3,
        "realized_pnl_pct": 5.2,
        "unrealized_pnl_pct": 3.1,
        "win_count": 2,
        "loss_count": 1
    }
}
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field

from config import SIGNATURES_FILE, RUNS_DIR, get_market_status
from prices import PriceFetcher


@dataclass
class Position:
    """A position within a signature"""
    ticker: str
    category: str  # strong_buy, buy, early_buy, dividend
    entry_price: float
    entry_date: str
    entry_type: str  # open, close, previous_close
    status: str = "open"  # open, closed
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason: Optional[str] = None  # sell_signal, manual
    pnl_pct: Optional[float] = None
    pnl_amt: Optional[float] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        return cls(**data)
    
    def close(self, price: float, reason: str = "sell_signal"):
        """Close this position"""
        self.status = "closed"
        self.exit_price = price
        self.exit_date = datetime.now().strftime("%Y-%m-%d")
        self.exit_reason = reason
        self.pnl_amt = price - self.entry_price
        self.pnl_pct = (self.pnl_amt / self.entry_price) * 100 if self.entry_price > 0 else 0


@dataclass
class Signature:
    """A complete run signature"""
    signature_id: str
    file_hash: str
    created_at: str
    mode: str
    market_status: str
    source_file: str  # Original filename
    positions: Dict[str, Position] = field(default_factory=dict)
    
    # Stored output
    output_file: str = ""
    
    def to_dict(self) -> dict:
        d = {
            'signature_id': self.signature_id,
            'file_hash': self.file_hash,
            'created_at': self.created_at,
            'mode': self.mode,
            'market_status': self.market_status,
            'source_file': self.source_file,
            'output_file': self.output_file,
            'positions': {t: p.to_dict() for t, p in self.positions.items()}
        }
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Signature':
        positions = {
            t: Position.from_dict(p) 
            for t, p in data.get('positions', {}).items()
        }
        return cls(
            signature_id=data['signature_id'],
            file_hash=data['file_hash'],
            created_at=data['created_at'],
            mode=data['mode'],
            market_status=data.get('market_status', ''),
            source_file=data.get('source_file', ''),
            output_file=data.get('output_file', ''),
            positions=positions
        )
    
    def get_summary(self) -> dict:
        """Calculate current summary statistics"""
        open_positions = [p for p in self.positions.values() if p.status == "open"]
        closed_positions = [p for p in self.positions.values() if p.status == "closed"]
        
        winners = [p for p in closed_positions if (p.pnl_pct or 0) > 0]
        losers = [p for p in closed_positions if (p.pnl_pct or 0) <= 0]
        
        realized_pnl = sum(p.pnl_pct or 0 for p in closed_positions)
        
        return {
            'total_positions': len(self.positions),
            'open_positions': len(open_positions),
            'closed_positions': len(closed_positions),
            'realized_pnl_pct': realized_pnl,
            'win_count': len(winners),
            'loss_count': len(losers),
            'win_rate': len(winners) / len(closed_positions) * 100 if closed_positions else 0
        }
    
    def get_open_tickers(self) -> List[str]:
        """Get list of tickers with open positions"""
        return [t for t, p in self.positions.items() if p.status == "open"]
    
    def close_position(self, ticker: str, price: float, reason: str = "sell_signal") -> bool:
        """Close a position by ticker"""
        if ticker in self.positions and self.positions[ticker].status == "open":
            self.positions[ticker].close(price, reason)
            return True
        return False


class SignatureManager:
    """Manages all signatures"""
    
    def __init__(self):
        self.signatures: Dict[str, Signature] = {}  # signature_id -> Signature
        self.hash_index: Dict[str, str] = {}  # file_hash -> signature_id
        self._load()
    
    def _load(self):
        """Load signatures from disk"""
        if SIGNATURES_FILE.exists():
            with open(SIGNATURES_FILE) as f:
                data = json.load(f)
                
            for sig_data in data.get('signatures', []):
                sig = Signature.from_dict(sig_data)
                self.signatures[sig.signature_id] = sig
                self.hash_index[sig.file_hash] = sig.signature_id
    
    def _save(self):
        """Save signatures to disk"""
        data = {
            'signatures': [sig.to_dict() for sig in self.signatures.values()],
            'updated_at': datetime.now().isoformat()
        }
        with open(SIGNATURES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def compute_file_hash(self, content: str, mode: str = '') -> str:
        """
        Compute hash of file content + mode.
        Same file with different modes = different signatures.
        """
        combined = f"{content}:{mode}"
        return f"sha256:{hashlib.sha256(combined.encode()).hexdigest()}"
    
    def get_by_hash(self, file_hash: str) -> Optional[Signature]:
        """Get signature by file hash (returns existing if file was seen before)"""
        if file_hash in self.hash_index:
            sig_id = self.hash_index[file_hash]
            return self.signatures.get(sig_id)
        return None
    
    def get_by_id(self, signature_id: str) -> Optional[Signature]:
        """Get signature by ID (supports partial match)"""
        # Exact match
        if signature_id in self.signatures:
            return self.signatures[signature_id]
        
        # Partial match
        matches = [s for s in self.signatures.keys() if s.startswith(signature_id)]
        if len(matches) == 1:
            return self.signatures[matches[0]]
        elif len(matches) > 1:
            print(f"Multiple matches for '{signature_id}':")
            for m in matches[:5]:
                print(f"  {m}")
        
        return None
    
    def create_signature(self, 
                         file_content: str,
                         source_file: str,
                         mode: str,
                         parsed_stocks: Dict[str, List[str]]) -> Tuple[Signature, bool]:
        """
        Create a new signature or return existing one if file was seen before.
        
        Args:
            file_content: Raw file content
            source_file: Original filename
            mode: Trading mode (strong, early, all, dividend)
            parsed_stocks: Dict with keys: strong_buys, early_buys, dividends, buys, sells
        
        Returns:
            Tuple of (Signature, is_new)
        """
        file_hash = self.compute_file_hash(file_content, mode)
        
        # Check if file was already processed
        existing = self.get_by_hash(file_hash)
        if existing:
            return existing, False
        
        # Create new signature
        now = datetime.now()
        market = get_market_status()
        
        signature_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{file_hash[7:15]}"
        
        # Get entry prices for buy signals based on mode
        buy_tickers = []
        ticker_categories = {}
        
        if mode in ['strong', 'all']:
            for t in parsed_stocks.get('strong_buys', []):
                buy_tickers.append(t)
                ticker_categories[t] = 'strong_buy'
        
        if mode in ['early', 'all']:
            for t in parsed_stocks.get('early_buys', []):
                if t not in ticker_categories:  # Don't duplicate
                    buy_tickers.append(t)
                    ticker_categories[t] = 'early_buy'
        
        if mode == 'dividend':
            for t in parsed_stocks.get('dividends', []):
                buy_tickers.append(t)
                ticker_categories[t] = 'dividend'
        
        # Fetch entry prices
        fetcher = PriceFetcher()
        price_data = fetcher.get_entry_prices(buy_tickers)
        
        # Create positions
        positions = {}
        for ticker in buy_tickers:
            if ticker in price_data:
                pd = price_data[ticker]
                positions[ticker] = Position(
                    ticker=ticker,
                    category=ticker_categories[ticker],
                    entry_price=pd['price'],
                    entry_date=pd['date'],
                    entry_type=pd['price_type']
                )
        
        # Save raw output
        run_dir = RUNS_DIR / now.strftime('%Y%m%d')
        run_dir.mkdir(parents=True, exist_ok=True)
        output_file = run_dir / f"{signature_id}.txt"
        with open(output_file, 'w') as f:
            f.write(file_content)
        
        # Create signature
        sig = Signature(
            signature_id=signature_id,
            file_hash=file_hash,
            created_at=now.isoformat(),
            mode=mode,
            market_status=market['description'],
            source_file=source_file,
            output_file=str(output_file.relative_to(RUNS_DIR)),
            positions=positions
        )
        
        # Store
        self.signatures[signature_id] = sig
        self.hash_index[file_hash] = signature_id
        self._save()
        
        return sig, True
    
    def update_signature(self, signature: Signature):
        """Save updates to a signature"""
        self.signatures[signature.signature_id] = signature
        self._save()
    
    def list_all(self, 
                 mode: Optional[str] = None,
                 limit: int = 50) -> List[Signature]:
        """List all signatures, optionally filtered by mode"""
        results = list(self.signatures.values())
        
        if mode and mode != 'all':
            results = [s for s in results if s.mode == mode]
        
        # Sort by date, newest first
        results.sort(key=lambda x: x.created_at, reverse=True)
        
        return results[:limit]
    
    def get_all_open_positions(self) -> Dict[str, List[Tuple[str, Position]]]:
        """
        Get all open positions across all signatures.
        Returns dict of ticker -> [(signature_id, Position), ...]
        """
        open_positions = {}
        
        for sig_id, sig in self.signatures.items():
            for ticker, pos in sig.positions.items():
                if pos.status == "open":
                    if ticker not in open_positions:
                        open_positions[ticker] = []
                    open_positions[ticker].append((sig_id, pos))
        
        return open_positions
    
    def get_output_content(self, signature_id: str) -> Optional[str]:
        """Get stored output content for a signature"""
        sig = self.get_by_id(signature_id)
        if not sig or not sig.output_file:
            return None
        
        output_path = RUNS_DIR / sig.output_file
        if output_path.exists():
            with open(output_path) as f:
                return f.read()
        return None
    
    def delete_signature(self, signature_id: str) -> bool:
        """Delete a signature"""
        sig = self.get_by_id(signature_id)
        if not sig:
            return False
        
        # Remove output file
        if sig.output_file:
            output_path = RUNS_DIR / sig.output_file
            output_path.unlink(missing_ok=True)
        
        # Remove from index
        if sig.file_hash in self.hash_index:
            del self.hash_index[sig.file_hash]
        
        del self.signatures[sig.signature_id]
        self._save()
        
        return True


if __name__ == '__main__':
    # Test
    mgr = SignatureManager()
    
    print(f"Loaded {len(mgr.signatures)} signatures")
    
    for sig in mgr.list_all(limit=5):
        summary = sig.get_summary()
        print(f"\n{sig.signature_id}")
        print(f"  Created: {sig.created_at}")
        print(f"  Mode: {sig.mode}")
        print(f"  Positions: {summary['total_positions']} "
              f"({summary['open_positions']} open, {summary['closed_positions']} closed)")
        print(f"  Realized P/L: {summary['realized_pnl_pct']:.1f}%")
