"""
Portfolio Positions Manager
===========================

Loads actual portfolio positions from mypositions.csv (Fidelity export).
Provides cost basis for P&L calculations.
"""

import csv
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

from config import POSITIONS_FILE


@dataclass
class Position:
    """A portfolio position with cost basis"""
    symbol: str
    value: float           # Current value
    cost_basis: float      # What you paid
    num_accounts: int      # How many accounts hold this
    
    @property
    def pnl_dollar(self) -> float:
        """P&L in dollars"""
        return self.value - self.cost_basis
    
    @property
    def pnl_percent(self) -> float:
        """P&L as percentage"""
        if self.cost_basis <= 0:
            return 0.0
        return ((self.value - self.cost_basis) / self.cost_basis) * 100
    
    @property
    def avg_cost(self) -> float:
        """Average cost per share (approximate)"""
        # We don't have share count, but we can estimate
        # This is just cost_basis since we don't track quantity here
        return self.cost_basis


class PositionsManager:
    """Load and query portfolio positions"""
    
    def __init__(self, positions_file: Optional[Path] = None):
        self.positions_file = positions_file or POSITIONS_FILE
        self._positions: Dict[str, Position] = {}
        self._loaded = False
    
    def load(self) -> bool:
        """Load positions from CSV file"""
        if not self.positions_file.exists():
            print(f"⚠️  Positions file not found: {self.positions_file}")
            return False
        
        try:
            with open(self.positions_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get('Symbol', '').strip()
                    if not symbol:
                        continue
                    
                    try:
                        value = float(row.get('Value', 0))
                        cost_basis = float(row.get('CostBasis', 0))
                        num_accounts = int(row.get('NumAccounts', 1))
                    except (ValueError, TypeError):
                        continue
                    
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        value=value,
                        cost_basis=cost_basis,
                        num_accounts=num_accounts
                    )
            
            self._loaded = True
            return True
            
        except Exception as e:
            print(f"❌ Error loading positions: {e}")
            return False
    
    def get(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol"""
        if not self._loaded:
            self.load()
        return self._positions.get(symbol)
    
    def get_cost_basis(self, symbol: str) -> Optional[float]:
        """Get cost basis for a symbol"""
        pos = self.get(symbol)
        return pos.cost_basis if pos else None
    
    def get_all(self) -> Dict[str, Position]:
        """Get all positions"""
        if not self._loaded:
            self.load()
        return self._positions.copy()
    
    def calculate_pnl(self, symbol: str, current_price: float, quantity: float = None) -> dict:
        """
        Calculate P&L for a position.
        
        If quantity not provided, uses cost basis directly.
        """
        pos = self.get(symbol)
        if not pos:
            return {
                'symbol': symbol,
                'has_position': False,
                'cost_basis': None,
                'pnl_percent': None
            }
        
        # If we have cost basis, calculate P&L
        # Note: We're using the stored cost basis, not current_price * quantity
        # because we don't have share counts in this simple format
        return {
            'symbol': symbol,
            'has_position': True,
            'cost_basis': pos.cost_basis,
            'current_value': pos.value,
            'pnl_dollar': pos.pnl_dollar,
            'pnl_percent': pos.pnl_percent
        }
    
    def __len__(self):
        if not self._loaded:
            self.load()
        return len(self._positions)
    
    def __contains__(self, symbol: str):
        if not self._loaded:
            self.load()
        return symbol in self._positions


# Convenience function
def load_positions(positions_file: Optional[Path] = None) -> Dict[str, Position]:
    """Load positions and return as dict"""
    mgr = PositionsManager(positions_file)
    mgr.load()
    return mgr.get_all()
