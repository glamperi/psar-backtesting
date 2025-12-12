#!/usr/bin/env python3
"""
PSAR Backtesting CLI
====================

Process scanner output files, track positions, measure P/L.

COMMANDS:
---------
    process FILE    Process a scanner output file, create/update signature
    signatures      List all signatures with P/L summary
    report SIG      Show detailed report for a signature
    check-sells     Check open positions for sells (calls scanner)
    live            Show live P/L with current quotes
    close TICKER    Manually close a position in a signature
    show SIG        Show stored output for a signature
    reset           Clear all data

MODES:
------
    -m strong       Strong Buy signals only
    -m early        Early Buy signals only  
    -m all          Both Strong and Early (default)
    -m dividend     Dividend stocks only

EXAMPLES:
---------
    python bt.py process scanner_output.html --mode strong
    python bt.py signatures
    python bt.py report 20251212
    python bt.py check-sells
    python bt.py live
    python bt.py close NVDA --signature 20251212
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import get_market_status, DATA_DIR
from signatures import SignatureManager, Signature
from file_parser import parse_file, parse_content, get_buy_tickers
from scanner_bridge import ScannerBridge
from prices import PriceFetcher


class BacktestCLI:
    """Main CLI handler"""
    
    def __init__(self):
        self.sig_mgr = SignatureManager()
        self.scanner = ScannerBridge()
        self.prices = PriceFetcher()
    
    # =========================================================================
    # PROCESS FILE
    # =========================================================================
    
    def cmd_process(self, filepath: str, mode: str = 'all') -> dict:
        """
        Process a scanner output file.
        
        - If file was seen before (same content), returns existing signature
        - If new file, creates signature with entry prices based on market timing
        """
        path = Path(filepath)
        if not path.exists():
            return {'success': False, 'error': f"File not found: {filepath}"}
        
        print(f"📄 Processing: {path.name}")
        
        # Read file
        with open(path, encoding='utf-8') as f:
            content = f.read()
        
        # Parse stocks
        parsed = parse_content(content)
        
        buy_tickers = get_buy_tickers(parsed, mode)
        print(f"   Mode: {mode}")
        print(f"   Found: {len(parsed.get('strong_buys', []))} Strong Buy, "
              f"{len(parsed.get('early_buys', []))} Early Buy, "
              f"{len(parsed.get('dividends', []))} Dividend, "
              f"{len(parsed.get('sells', []))} Sell")
        print(f"   Tracking: {len(buy_tickers)} positions in {mode} mode")
        
        # Create or get signature
        sig, is_new = self.sig_mgr.create_signature(
            file_content=content,
            source_file=path.name,
            mode=mode,
            parsed_stocks=parsed
        )
        
        if is_new:
            print(f"\n✅ NEW signature created: {sig.signature_id}")
            print(f"   Market: {sig.market_status}")
            print(f"   Positions: {len(sig.positions)}")
            
            # Show entry prices
            print(f"\n   Entry prices:")
            for ticker, pos in list(sig.positions.items())[:10]:
                print(f"      {ticker}: ${pos.entry_price:.2f} ({pos.entry_type})")
            if len(sig.positions) > 10:
                print(f"      ... and {len(sig.positions) - 10} more")
        else:
            summary = sig.get_summary()
            print(f"\n📎 EXISTING signature found: {sig.signature_id}")
            print(f"   Created: {sig.created_at}")
            print(f"   Positions: {summary['open_positions']} open, "
                  f"{summary['closed_positions']} closed")
            print(f"   Realized P/L: {summary['realized_pnl_pct']:.1f}%")
        
        return {
            'success': True,
            'signature': sig.signature_id,
            'is_new': is_new,
            'positions': len(sig.positions)
        }
    
    # =========================================================================
    # SIGNATURES LIST
    # =========================================================================
    
    def cmd_signatures(self, mode: Optional[str] = None, limit: int = 20) -> str:
        """List all signatures with P/L summary"""
        sigs = self.sig_mgr.list_all(mode=mode, limit=limit)
        
        if not sigs:
            return "📭 No signatures found.\n\nUse 'bt.py process <file>' to create one."
        
        # Fetch current prices for unrealized P/L
        all_open_tickers = set()
        for sig in sigs:
            all_open_tickers.update(sig.get_open_tickers())
        
        current_prices = {}
        if all_open_tickers:
            current_prices = self.prices.get_current_prices(list(all_open_tickers))
        
        lines = []
        lines.append(f"\n📋 SIGNATURES ({len(sigs)})")
        lines.append("=" * 100)
        lines.append(f"{'ID':<28} {'Date':<12} {'Mode':<8} {'Open':<6} "
                    f"{'Closed':<8} {'Realized':<10} {'Unrealized':<12} {'Total':<10}")
        lines.append("-" * 100)
        
        for sig in sigs:
            summary = sig.get_summary()
            
            # Calculate unrealized P/L
            unrealized = 0.0
            for ticker, pos in sig.positions.items():
                if pos.status == "open" and ticker in current_prices:
                    pnl = ((current_prices[ticker] - pos.entry_price) / pos.entry_price) * 100
                    unrealized += pnl
            
            total = summary['realized_pnl_pct'] + unrealized
            
            # Format
            realized_str = f"{summary['realized_pnl_pct']:+.1f}%" if summary['closed_positions'] > 0 else "-"
            unrealized_str = f"{unrealized:+.1f}%" if summary['open_positions'] > 0 else "-"
            total_str = f"{total:+.1f}%"
            
            # Win/loss indicator
            if summary['closed_positions'] > 0:
                win_loss = f"({summary['win_count']}/{summary['closed_positions']})"
            else:
                win_loss = ""
            
            lines.append(
                f"{sig.signature_id:<28} "
                f"{sig.created_at[:10]:<12} "
                f"{sig.mode:<8} "
                f"{summary['open_positions']:<6} "
                f"{summary['closed_positions']:<8} "
                f"{realized_str:<10} "
                f"{unrealized_str:<12} "
                f"{total_str:<10}"
            )
        
        lines.append("-" * 100)
        lines.append(f"\nUse 'bt.py report <signature>' for detailed view")
        lines.append(f"Use 'bt.py live' for real-time P/L")
        
        return "\n".join(lines)
    
    # =========================================================================
    # DETAILED REPORT
    # =========================================================================
    
    def cmd_report(self, signature_id: str) -> str:
        """Show detailed report for a signature"""
        sig = self.sig_mgr.get_by_id(signature_id)
        
        if not sig:
            return f"❌ Signature not found: {signature_id}"
        
        summary = sig.get_summary()
        
        # Fetch current prices
        open_tickers = sig.get_open_tickers()
        current_prices = self.prices.get_current_prices(open_tickers) if open_tickers else {}
        
        lines = []
        lines.append("=" * 80)
        lines.append(f"📊 SIGNATURE REPORT: {sig.signature_id}")
        lines.append("=" * 80)
        lines.append(f"Created: {sig.created_at}")
        lines.append(f"Source: {sig.source_file}")
        lines.append(f"Mode: {sig.mode}")
        lines.append(f"Market: {sig.market_status}")
        lines.append("-" * 80)
        
        # Summary
        lines.append(f"\n📈 SUMMARY")
        lines.append(f"   Total Positions: {summary['total_positions']}")
        lines.append(f"   Open: {summary['open_positions']}")
        lines.append(f"   Closed: {summary['closed_positions']}")
        if summary['closed_positions'] > 0:
            lines.append(f"   Win Rate: {summary['win_count']}/{summary['closed_positions']} "
                        f"({summary['win_rate']:.1f}%)")
            lines.append(f"   Realized P/L: {summary['realized_pnl_pct']:+.1f}%")
        
        # Open positions
        open_positions = [p for p in sig.positions.values() if p.status == "open"]
        if open_positions:
            lines.append(f"\n🟢 OPEN POSITIONS ({len(open_positions)})")
            lines.append("-" * 80)
            lines.append(f"{'Ticker':<8} {'Category':<12} {'Entry$':<10} "
                        f"{'Current$':<10} {'P/L%':<10} {'Entry Date':<12}")
            lines.append("-" * 80)
            
            total_unrealized = 0
            for pos in sorted(open_positions, key=lambda x: x.entry_date):
                current = current_prices.get(pos.ticker, pos.entry_price)
                pnl = ((current - pos.entry_price) / pos.entry_price) * 100
                total_unrealized += pnl
                
                emoji = "🟢" if pnl > 0 else "🔴"
                lines.append(f"{pos.ticker:<8} {pos.category:<12} "
                            f"${pos.entry_price:<9.2f} ${current:<9.2f} "
                            f"{emoji}{pnl:>+6.1f}%   {pos.entry_date:<12}")
            
            lines.append("-" * 80)
            avg = total_unrealized / len(open_positions)
            lines.append(f"{'Unrealized Total:':<42} {total_unrealized:>+8.1f}% "
                        f"(avg {avg:+.1f}%)")
        
        # Closed positions
        closed_positions = [p for p in sig.positions.values() if p.status == "closed"]
        if closed_positions:
            lines.append(f"\n📉 CLOSED POSITIONS ({len(closed_positions)})")
            lines.append("-" * 80)
            lines.append(f"{'Ticker':<8} {'Entry$':<10} {'Exit$':<10} "
                        f"{'P/L%':<10} {'Reason':<12} {'Dates':<20}")
            lines.append("-" * 80)
            
            for pos in sorted(closed_positions, key=lambda x: x.exit_date or '', reverse=True):
                emoji = "🟢" if (pos.pnl_pct or 0) > 0 else "🔴"
                dates = f"{pos.entry_date} → {pos.exit_date}"
                lines.append(f"{pos.ticker:<8} ${pos.entry_price:<9.2f} "
                            f"${pos.exit_price or 0:<9.2f} "
                            f"{emoji}{pos.pnl_pct or 0:>+6.1f}%   "
                            f"{pos.exit_reason or '':<12} {dates:<20}")
            
            lines.append("-" * 80)
            lines.append(f"{'Realized Total:':<42} {summary['realized_pnl_pct']:>+8.1f}%")
        
        lines.append("\n" + "=" * 80)
        
        return "\n".join(lines)
    
    # =========================================================================
    # CHECK SELLS
    # =========================================================================
    
    def cmd_check_sells(self, from_file: Optional[str] = None) -> dict:
        """
        Check all open positions for sells.
        
        If from_file provided, parses that file for sells (fast).
        Otherwise, calls the scanner to check live (slow).
        """
        print("🔍 Checking open positions for sells...")
        
        # Get all open positions across all signatures
        all_open = self.sig_mgr.get_all_open_positions()
        
        if not all_open:
            print("📭 No open positions to check")
            return {'success': True, 'closed': 0}
        
        tickers = list(all_open.keys())
        print(f"   Checking {len(tickers)} tickers...")
        
        # Find sells - either from file or by calling scanner
        if from_file:
            # Parse existing file (fast)
            from scanner_bridge import detect_sells_from_file
            filepath = Path(from_file)
            if not filepath.exists():
                print(f"❌ File not found: {from_file}")
                return {'success': False, 'error': 'File not found'}
            
            content = filepath.read_text()
            sells = detect_sells_from_file(content, tickers)
            print(f"   (Using file: {filepath.name})")
        else:
            # Call scanner (slow - has to download data)
            sells = self.scanner.find_sells(tickers)
        
        if not sells:
            print("✅ No positions in Sell zone")
            return {'success': True, 'closed': 0}
        
        print(f"   Found {len(sells)} in Sell zone: {', '.join(sells)}")
        
        # Get exit prices
        exit_prices = self.prices.get_current_prices(list(sells))
        
        # Close positions
        closed_count = 0
        closed_details = []
        
        for ticker in sells:
            if ticker not in exit_prices:
                continue
            
            price = exit_prices[ticker]
            
            # Close in all signatures that have this open
            for sig_id, pos in all_open.get(ticker, []):
                sig = self.sig_mgr.get_by_id(sig_id)
                if sig and sig.close_position(ticker, price, "sell_signal"):
                    self.sig_mgr.update_signature(sig)
                    closed_count += 1
                    
                    pnl = ((price - pos.entry_price) / pos.entry_price) * 100
                    closed_details.append({
                        'ticker': ticker,
                        'signature': sig_id,
                        'entry': pos.entry_price,
                        'exit': price,
                        'pnl': pnl
                    })
        
        # Report
        if closed_details:
            print(f"\n📉 Closed {closed_count} positions:")
            for d in closed_details:
                emoji = "🟢" if d['pnl'] > 0 else "🔴"
                print(f"   {emoji} {d['ticker']}: ${d['entry']:.2f} → ${d['exit']:.2f} "
                      f"({d['pnl']:+.1f}%) in {d['signature'][:20]}")
        
        return {'success': True, 'closed': closed_count, 'details': closed_details}
    
    # =========================================================================
    # LIVE P/L
    # =========================================================================
    
    def cmd_live(self) -> str:
        """Show live P/L with current quotes for all signatures"""
        sigs = self.sig_mgr.list_all(limit=100)
        
        if not sigs:
            return "📭 No signatures found."
        
        # Get all unique open tickers
        all_open = {}
        for sig in sigs:
            for ticker, pos in sig.positions.items():
                if pos.status == "open":
                    if ticker not in all_open:
                        all_open[ticker] = []
                    all_open[ticker].append((sig.signature_id, pos))
        
        if not all_open:
            return "📭 No open positions."
        
        # Get current quotes
        print("📡 Fetching live quotes...")
        quotes = self.prices.get_intraday_quotes(list(all_open.keys()))
        
        market = get_market_status()
        
        lines = []
        lines.append("=" * 90)
        lines.append(f"📈 LIVE P/L - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"   Market: {market['description']}")
        lines.append("=" * 90)
        
        lines.append(f"\n{'Ticker':<8} {'Current$':<10} {'Change':<10} "
                    f"{'Positions':<10} {'Avg Entry':<12} {'P/L%':<10}")
        lines.append("-" * 90)
        
        total_pnl = 0
        total_positions = 0
        
        for ticker in sorted(all_open.keys()):
            positions = all_open[ticker]
            quote = quotes.get(ticker, {})
            
            current = quote.get('price') or 0
            if not current:
                continue
            
            # Average entry across signatures
            total_entry = sum(pos.entry_price for _, pos in positions)
            avg_entry = total_entry / len(positions)
            
            # P/L
            pnl = ((current - avg_entry) / avg_entry) * 100
            total_pnl += pnl * len(positions)
            total_positions += len(positions)
            
            # Day change
            change = quote.get('change_pct')
            change_str = f"{change:+.1f}%" if change else "-"
            
            emoji = "🟢" if pnl > 0 else "🔴"
            
            lines.append(f"{ticker:<8} ${current:<9.2f} {change_str:<10} "
                        f"{len(positions):<10} ${avg_entry:<11.2f} {emoji}{pnl:>+6.1f}%")
        
        lines.append("-" * 90)
        avg_pnl = total_pnl / total_positions if total_positions > 0 else 0
        lines.append(f"{'TOTAL':<8} {'':<10} {'':<10} "
                    f"{total_positions:<10} {'':<12} {avg_pnl:>+6.1f}%")
        
        lines.append("\n" + "=" * 90)
        
        return "\n".join(lines)
    
    # =========================================================================
    # MANUAL CLOSE
    # =========================================================================
    
    def cmd_close(self, ticker: str, signature_id: Optional[str] = None, 
                  price: Optional[float] = None) -> dict:
        """Manually close a position"""
        ticker = ticker.upper()
        
        # Find positions with this ticker
        if signature_id:
            sig = self.sig_mgr.get_by_id(signature_id)
            if not sig:
                return {'success': False, 'error': f"Signature not found: {signature_id}"}
            
            if ticker not in sig.positions or sig.positions[ticker].status != "open":
                return {'success': False, 'error': f"No open position for {ticker} in {signature_id}"}
            
            targets = [(sig.signature_id, sig)]
        else:
            # Find all signatures with this ticker open
            targets = []
            for sig in self.sig_mgr.list_all(limit=100):
                if ticker in sig.positions and sig.positions[ticker].status == "open":
                    targets.append((sig.signature_id, sig))
            
            if not targets:
                return {'success': False, 'error': f"No open position for {ticker}"}
        
        # Get exit price
        if price is None:
            prices = self.prices.get_current_prices([ticker])
            if ticker not in prices:
                return {'success': False, 'error': f"Could not fetch price for {ticker}"}
            price = prices[ticker]
        
        # Close positions
        closed = []
        for sig_id, sig in targets:
            pos = sig.positions[ticker]
            entry = pos.entry_price
            
            sig.close_position(ticker, price, "manual")
            self.sig_mgr.update_signature(sig)
            
            pnl = ((price - entry) / entry) * 100
            closed.append({
                'signature': sig_id,
                'entry': entry,
                'exit': price,
                'pnl': pnl
            })
        
        # Report
        print(f"✅ Closed {ticker} in {len(closed)} signature(s)")
        for c in closed:
            emoji = "🟢" if c['pnl'] > 0 else "🔴"
            print(f"   {emoji} {c['signature'][:25]}: ${c['entry']:.2f} → ${c['exit']:.2f} "
                  f"({c['pnl']:+.1f}%)")
        
        return {'success': True, 'closed': closed}
    
    # =========================================================================
    # SHOW OUTPUT
    # =========================================================================
    
    def cmd_show(self, signature_id: str) -> str:
        """Show stored output for a signature"""
        content = self.sig_mgr.get_output_content(signature_id)
        
        if content is None:
            return f"❌ Signature not found or output missing: {signature_id}"
        
        sig = self.sig_mgr.get_by_id(signature_id)
        
        lines = []
        lines.append(f"\n📄 OUTPUT: {sig.signature_id}")
        lines.append(f"   Source: {sig.source_file}")
        lines.append(f"   Date: {sig.created_at}")
        lines.append("=" * 80)
        lines.append(content[:8000])
        if len(content) > 8000:
            lines.append(f"\n... truncated ({len(content)} total chars)")
        
        return "\n".join(lines)
    
    # =========================================================================
    # HTML REPORT
    # =========================================================================
    
    def cmd_html(self, signature_id: Optional[str] = None, output_dir: Optional[str] = None) -> dict:
        """
        Generate HTML reports.
        
        If signature_id provided, generates single report.
        Otherwise generates index + all reports.
        """
        from html_report import save_report, save_signatures_index
        from pathlib import Path
        
        out_path = Path(output_dir) if output_dir else None
        
        if signature_id:
            # Single report
            sig = self.sig_mgr.get_by_id(signature_id)
            if not sig:
                return {'success': False, 'error': f"Signature not found: {signature_id}"}
            
            # Get current prices
            open_tickers = sig.get_open_tickers()
            current_prices = self.prices.get_current_prices(open_tickers) if open_tickers else {}
            
            filepath = save_report(sig, current_prices, out_path)
            print(f"✅ Report saved: {filepath}")
            return {'success': True, 'file': str(filepath)}
        
        else:
            # All reports + index
            sigs = self.sig_mgr.list_all(limit=100)
            
            if not sigs:
                return {'success': False, 'error': "No signatures found"}
            
            # Get all open tickers
            all_open = set()
            for sig in sigs:
                all_open.update(sig.get_open_tickers())
            
            current_prices = self.prices.get_current_prices(list(all_open)) if all_open else {}
            
            # Generate index
            index_path = save_signatures_index(sigs, current_prices, out_path)
            print(f"✅ Index saved: {index_path}")
            
            # Generate individual reports
            for sig in sigs:
                filepath = save_report(sig, current_prices, out_path)
            
            print(f"✅ Generated {len(sigs)} reports")
            return {'success': True, 'count': len(sigs), 'index': str(index_path)}
    
    # =========================================================================
    # DELETE SIGNATURE
    # =========================================================================
    
    def cmd_delete(self, signature_id: str, confirm: bool = False) -> dict:
        """Delete a signature and its stored files"""
        sig = self.sig_mgr.get_by_id(signature_id)
        
        if not sig:
            return {'success': False, 'error': f"Signature not found: {signature_id}"}
        
        summary = sig.get_summary()
        
        if not confirm:
            print(f"⚠️  About to delete: {sig.signature_id}")
            print(f"   Created: {sig.created_at}")
            print(f"   Source: {sig.source_file}")
            print(f"   Positions: {summary['total_positions']} ({summary['open_positions']} open)")
            print(f"\n   Use --confirm to delete")
            return {'success': False, 'error': "Add --confirm to delete"}
        
        # Delete
        if self.sig_mgr.delete_signature(sig.signature_id):
            print(f"✅ Deleted: {sig.signature_id}")
            return {'success': True}
        else:
            return {'success': False, 'error': "Delete failed"}
    
    # =========================================================================
    # RESET
    # =========================================================================
    
    def cmd_reset(self, confirm: bool = False) -> dict:
        """Reset all data"""
        if not confirm:
            return {'success': False, 'error': "Use --confirm to reset all data"}
        
        import shutil
        
        # Clear data directory
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / 'runs').mkdir(exist_ok=True)
        
        # Reinitialize
        self.sig_mgr = SignatureManager()
        
        print("✅ All data reset")
        return {'success': True}


def main():
    parser = argparse.ArgumentParser(
        description="PSAR Backtesting CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  process FILE      Process scanner output file
  signatures        List all signatures with P/L
  report SIG        Show detailed report for signature  
  check-sells       Check open positions for sells
  live              Show live P/L with quotes
  close TICKER      Manually close a position
  show SIG          Show stored output
  reset             Clear all data

Examples:
  python bt.py process output.html --mode strong
  python bt.py signatures
  python bt.py report 20251212
  python bt.py check-sells
  python bt.py live
  python bt.py close NVDA --signature 20251212
        """
    )
    
    subparsers = parser.add_subparsers(dest='command')
    
    # process
    p_process = subparsers.add_parser('process', help='Process scanner output file')
    p_process.add_argument('file', help='Path to scanner output file')
    p_process.add_argument('-m', '--mode', choices=['strong', 'early', 'all', 'dividend'],
                           default='all', help='Trading mode')
    
    # signatures
    p_sigs = subparsers.add_parser('signatures', help='List all signatures')
    p_sigs.add_argument('-m', '--mode', choices=['strong', 'early', 'all', 'dividend'],
                        help='Filter by mode')
    p_sigs.add_argument('--limit', type=int, default=20, help='Max results')
    
    # report
    p_report = subparsers.add_parser('report', help='Show signature report')
    p_report.add_argument('signature', help='Signature ID (can be partial)')
    
    # check-sells
    p_sells = subparsers.add_parser('check-sells', help='Check for sells')
    p_sells.add_argument('-f', '--from-file', help='Use existing scanner output file (faster)')
    
    # live
    p_live = subparsers.add_parser('live', help='Show live P/L')
    
    # close
    p_close = subparsers.add_parser('close', help='Close position')
    p_close.add_argument('ticker', help='Ticker to close')
    p_close.add_argument('--signature', '-s', help='Specific signature (optional)')
    p_close.add_argument('--price', type=float, help='Exit price (optional)')
    
    # show
    p_show = subparsers.add_parser('show', help='Show stored output')
    p_show.add_argument('signature', help='Signature ID')
    
    # html
    p_html = subparsers.add_parser('html', help='Generate HTML reports')
    p_html.add_argument('signature', nargs='?', help='Signature ID (optional, generates all if omitted)')
    p_html.add_argument('-o', '--output', help='Output directory')
    
    # delete
    p_delete = subparsers.add_parser('delete', help='Delete a signature')
    p_delete.add_argument('signature', help='Signature ID to delete')
    p_delete.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    # reset
    p_reset = subparsers.add_parser('reset', help='Reset all data')
    p_reset.add_argument('--confirm', action='store_true', help='Confirm reset')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = BacktestCLI()
    
    if args.command == 'process':
        cli.cmd_process(args.file, args.mode)
    
    elif args.command == 'signatures':
        print(cli.cmd_signatures(args.mode, args.limit))
    
    elif args.command == 'report':
        print(cli.cmd_report(args.signature))
    
    elif args.command == 'check-sells':
        cli.cmd_check_sells(args.from_file)
    
    elif args.command == 'live':
        print(cli.cmd_live())
    
    elif args.command == 'close':
        cli.cmd_close(args.ticker, args.signature, args.price)
    
    elif args.command == 'show':
        print(cli.cmd_show(args.signature))
    
    elif args.command == 'html':
        cli.cmd_html(args.signature, args.output)
    
    elif args.command == 'delete':
        cli.cmd_delete(args.signature, args.confirm)
    
    elif args.command == 'reset':
        cli.cmd_reset(args.confirm)


if __name__ == '__main__':
    main()
