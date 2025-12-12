"""
HTML Report Generator
=====================
Creates pretty HTML reports for sharing backtest results.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from config import DATA_DIR


def generate_signature_report_html(signature, current_prices: Dict[str, float]) -> str:
    """
    Generate a pretty HTML report for a signature.
    
    Args:
        signature: Signature object
        current_prices: Dict of ticker -> current price
    
    Returns:
        HTML string
    """
    summary = signature.get_summary()
    
    # Calculate unrealized P/L (equal-weighted: average of all position returns)
    open_pnls = []
    open_positions = []
    closed_positions = []
    
    for ticker, pos in signature.positions.items():
        if pos.status == "open":
            current = current_prices.get(ticker, pos.entry_price)
            # Skip positions with invalid prices
            if pos.entry_price and pos.entry_price > 0 and current and current > 0:
                pnl = ((current - pos.entry_price) / pos.entry_price) * 100
                open_pnls.append(pnl)
            else:
                pnl = 0.0  # Can't calculate P/L
            open_positions.append({
                'ticker': ticker,
                'category': pos.category,
                'entry_price': pos.entry_price or 0,
                'entry_date': pos.entry_date,
                'current_price': current or 0,
                'pnl_pct': pnl
            })
        else:
            closed_positions.append({
                'ticker': ticker,
                'category': pos.category,
                'entry_price': pos.entry_price or 0,
                'entry_date': pos.entry_date,
                'exit_price': pos.exit_price,
                'exit_date': pos.exit_date,
                'pnl_pct': pos.pnl_pct or 0,
                'exit_reason': pos.exit_reason
            })
    
    # Equal-weighted average P/L
    avg_unrealized = sum(open_pnls) / len(open_pnls) if open_pnls else 0
    
    # Sort
    open_positions.sort(key=lambda x: x['pnl_pct'], reverse=True)
    closed_positions.sort(key=lambda x: x['exit_date'] or '', reverse=True)
    
    # Calculate realized P/L as average too
    closed_pnls = [p['pnl_pct'] for p in closed_positions]
    avg_realized = sum(closed_pnls) / len(closed_pnls) if closed_pnls else 0
    
    # Total P/L: weighted average based on position counts
    total_positions = len(open_positions) + len(closed_positions)
    if total_positions > 0:
        total_pnl = (avg_unrealized * len(open_positions) + avg_realized * len(closed_positions)) / total_positions
    else:
        total_pnl = 0
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Report - {signature.signature_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            color: #fff;
        }}
        .header .subtitle {{
            color: #888;
            font-size: 14px;
        }}
        .header .meta {{
            display: flex;
            gap: 30px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        .header .meta-item {{
            display: flex;
            flex-direction: column;
        }}
        .header .meta-label {{
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .header .meta-value {{
            font-size: 16px;
            color: #fff;
            margin-top: 4px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-card .label {{
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
            margin-top: 8px;
        }}
        .stat-card .sub {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}
        .positive {{ color: #00d4aa; }}
        .negative {{ color: #ff6b6b; }}
        .neutral {{ color: #ffd93d; }}
        
        .section {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .section h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section h2 .count {{
            background: rgba(255,255,255,0.1);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: normal;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            text-align: left;
            padding: 12px 15px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        td {{
            padding: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        tr:hover {{
            background: rgba(255,255,255,0.02);
        }}
        .ticker {{
            font-weight: bold;
            color: #fff;
            font-size: 15px;
        }}
        .category {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            text-transform: uppercase;
        }}
        .category.strong_buy {{ background: #1e8449; color: white; }}
        .category.early_buy {{ background: #2980b9; color: white; }}
        .category.buy {{ background: #27ae60; color: white; }}
        .category.dividend {{ background: #8e44ad; color: white; }}
        
        .price {{
            font-family: 'SF Mono', Monaco, monospace;
        }}
        .pnl {{
            font-weight: bold;
            font-size: 15px;
        }}
        
        .footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 12px;
        }}
        
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            table {{
                font-size: 13px;
            }}
            td, th {{
                padding: 10px 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Backtest Report</h1>
            <div class="subtitle">{signature.signature_id}</div>
            <div class="meta">
                <div class="meta-item">
                    <span class="meta-label">Created</span>
                    <span class="meta-value">{signature.created_at[:16].replace('T', ' ')}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Mode</span>
                    <span class="meta-value">{signature.mode.upper()}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Market</span>
                    <span class="meta-value">{signature.market_status}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Source</span>
                    <span class="meta-value">{signature.source_file}</span>
                </div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total P/L</div>
                <div class="value {'positive' if total_pnl > 0 else 'negative' if total_pnl < 0 else ''}">{total_pnl:+.2f}%</div>
                <div class="sub">Equal-weighted average</div>
            </div>
            <div class="stat-card">
                <div class="label">Realized P/L</div>
                <div class="value {'positive' if avg_realized > 0 else 'negative' if avg_realized < 0 else ''}">{avg_realized:+.2f}%</div>
                <div class="sub">{len(closed_positions)} closed trades</div>
            </div>
            <div class="stat-card">
                <div class="label">Unrealized P/L</div>
                <div class="value {'positive' if avg_unrealized > 0 else 'negative' if avg_unrealized < 0 else ''}">{avg_unrealized:+.2f}%</div>
                <div class="sub">{len(open_positions)} open positions</div>
            </div>
            <div class="stat-card">
                <div class="label">Win Rate</div>
                <div class="value">{summary['win_rate']:.0f}%</div>
                <div class="sub">{summary['win_count']}/{summary['closed_positions']} winners</div>
            </div>
        </div>
'''
    
    # Open positions section
    if open_positions:
        html += f'''
        <div class="section">
            <h2>🟢 Open Positions <span class="count">{len(open_positions)}</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Category</th>
                        <th>Entry Date</th>
                        <th>Entry Price</th>
                        <th>Current Price</th>
                        <th>P/L</th>
                    </tr>
                </thead>
                <tbody>
'''
        for pos in open_positions:
            pnl_class = 'positive' if pos['pnl_pct'] > 0 else 'negative' if pos['pnl_pct'] < 0 else ''
            html += f'''
                    <tr>
                        <td class="ticker">{pos['ticker']}</td>
                        <td><span class="category {pos['category']}">{pos['category'].replace('_', ' ')}</span></td>
                        <td>{pos['entry_date']}</td>
                        <td class="price">${pos['entry_price']:.2f}</td>
                        <td class="price">${pos['current_price']:.2f}</td>
                        <td class="pnl {pnl_class}">{pos['pnl_pct']:+.1f}%</td>
                    </tr>
'''
        html += '''
                </tbody>
            </table>
        </div>
'''
    
    # Closed positions section
    if closed_positions:
        html += f'''
        <div class="section">
            <h2>📉 Closed Positions <span class="count">{len(closed_positions)}</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Category</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>Entry $</th>
                        <th>Exit $</th>
                        <th>P/L</th>
                        <th>Reason</th>
                    </tr>
                </thead>
                <tbody>
'''
        for pos in closed_positions:
            pnl_class = 'positive' if pos['pnl_pct'] > 0 else 'negative' if pos['pnl_pct'] < 0 else ''
            html += f'''
                    <tr>
                        <td class="ticker">{pos['ticker']}</td>
                        <td><span class="category {pos['category']}">{pos['category'].replace('_', ' ')}</span></td>
                        <td>{pos['entry_date']}</td>
                        <td>{pos['exit_date'] or '-'}</td>
                        <td class="price">${pos['entry_price']:.2f}</td>
                        <td class="price">${pos['exit_price']:.2f if pos['exit_price'] else 0:.2f}</td>
                        <td class="pnl {pnl_class}">{pos['pnl_pct']:+.1f}%</td>
                        <td>{pos['exit_reason'] or '-'}</td>
                    </tr>
'''
        html += '''
                </tbody>
            </table>
        </div>
'''
    
    html += f'''
        <div class="footer">
            Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | PSAR Backtesting
        </div>
    </div>
</body>
</html>
'''
    
    return html


def generate_signatures_list_html(signatures: List, current_prices: Dict[str, float]) -> str:
    """
    Generate HTML for signatures list view.
    """
    html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Signatures</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { 
            font-size: 28px; 
            margin-bottom: 20px;
            color: #fff;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s, border-color 0.2s;
            cursor: pointer;
            text-decoration: none;
            color: inherit;
            display: block;
        }
        .card:hover {
            transform: translateY(-2px);
            border-color: rgba(255,255,255,0.2);
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }
        .card-id {
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 12px;
            color: #888;
        }
        .card-mode {
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            text-transform: uppercase;
        }
        .card-mode.strong { background: #1e8449; }
        .card-mode.early { background: #2980b9; }
        .card-mode.all { background: #8e44ad; }
        .card-mode.dividend { background: #f39c12; }
        .card-date {
            font-size: 14px;
            color: #aaa;
            margin-bottom: 15px;
        }
        .card-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }
        .stat {
            text-align: center;
            padding: 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
        }
        .stat-value {
            font-size: 20px;
            font-weight: bold;
        }
        .stat-label {
            font-size: 10px;
            color: #666;
            text-transform: uppercase;
            margin-top: 4px;
        }
        .positive { color: #00d4aa; }
        .negative { color: #ff6b6b; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Backtest Signatures</h1>
        <div class="grid">
'''
    
    for sig in signatures:
        summary = sig.get_summary()
        
        # Calculate unrealized as average (equal-weighted)
        open_pnls = []
        for ticker, pos in sig.positions.items():
            if pos.status == "open" and ticker in current_prices:
                entry = pos.entry_price or 0
                current = current_prices.get(ticker, 0)
                if entry > 0 and current > 0:
                    pnl = ((current - entry) / entry) * 100
                    open_pnls.append(pnl)
        
        avg_unrealized = sum(open_pnls) / len(open_pnls) if open_pnls else 0
        
        # Calculate realized as average
        closed_pnls = [pos.pnl_pct for pos in sig.positions.values() 
                       if pos.status == "closed" and pos.pnl_pct is not None]
        avg_realized = sum(closed_pnls) / len(closed_pnls) if closed_pnls else 0
        
        # Total P/L: weighted average
        total_positions = len(open_pnls) + len(closed_pnls)
        if total_positions > 0:
            total_pnl = (avg_unrealized * len(open_pnls) + avg_realized * len(closed_pnls)) / total_positions
        else:
            total_pnl = 0
        
        pnl_class = 'positive' if total_pnl > 0 else 'negative' if total_pnl < 0 else ''
        
        html += f'''
            <a href="report_{sig.signature_id}.html" class="card">
                <div class="card-header">
                    <span class="card-id">{sig.signature_id}</span>
                    <span class="card-mode {sig.mode}">{sig.mode}</span>
                </div>
                <div class="card-date">📅 {sig.created_at[:10]} &nbsp; 📄 {sig.source_file}</div>
                <div class="card-stats">
                    <div class="stat">
                        <div class="stat-value {pnl_class}">{total_pnl:+.1f}%</div>
                        <div class="stat-label">Total P/L</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{summary['open_positions']}</div>
                        <div class="stat-label">Open</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{summary['closed_positions']}</div>
                        <div class="stat-label">Closed</div>
                    </div>
                </div>
            </a>
'''
    
    html += '''
        </div>
    </div>
</body>
</html>
'''
    
    return html


def save_report(signature, current_prices: Dict[str, float], 
                output_dir: Optional[Path] = None) -> Path:
    """
    Save HTML report for a signature.
    
    Returns path to saved file.
    """
    if output_dir is None:
        output_dir = DATA_DIR / 'reports'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    html = generate_signature_report_html(signature, current_prices)
    
    filepath = output_dir / f"report_{signature.signature_id}.html"
    with open(filepath, 'w') as f:
        f.write(html)
    
    return filepath


def save_signatures_index(signatures: List, current_prices: Dict[str, float],
                          output_dir: Optional[Path] = None) -> Path:
    """
    Save HTML index of all signatures.
    """
    if output_dir is None:
        output_dir = DATA_DIR / 'reports'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    html = generate_signatures_list_html(signatures, current_prices)
    
    filepath = output_dir / "index.html"
    with open(filepath, 'w') as f:
        f.write(html)
    
    return filepath
