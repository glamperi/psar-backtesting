# PSAR Backtesting

Track performance of PSAR scanner signals over time. Process scanner output files, track positions with proper entry prices, and measure P/L with pretty HTML reports.

## Key Concepts

### File-Based Signatures
Each unique scanner output file + mode gets ONE signature. Process the same file twice = same signature, uses stored data. This ensures consistent backtesting.

### Market-Aware Entry Prices
Entry prices are determined by when you process the file:
- **Pre-market (before 9:30 AM ET)**: Previous day's close
- **Intraday (9:30 AM - 4:00 PM ET)**: Today's open  
- **After hours (after 4:00 PM ET)**: Today's close

### Scanner Independence
Stock names and prices are stored at processing time. The scanner is only called to detect sells for open positions - not for historical lookups.

## Portfolio Positions (Cost Basis)

The backtester can use your **actual cost basis** from Fidelity to calculate real P&L on sell signals.

### Setup

1. **Export from Fidelity** → Download "Portfolio Positions" CSV
2. **Extract positions** → Create `mypositions.csv` with:
   ```csv
   Symbol,Value,CostBasis,NumAccounts
   NVDA,275689.75,292645.12,2
   MSTR,42996.98,84525.81,1
   AMD,96377.25,101048.25,1
   ```
3. **Place in scanner data directory:**
   ```
   market-psar-scanner/data/mypositions.csv
   ```

### How It's Used

When you run `bt.py check-sells --preview`:
1. Loads `mypositions.csv` for cost basis
2. Matches against signatures.json for signal dates
3. Calculates P&L: `(Current Value - Cost Basis) / Cost Basis`
4. Shows tax loss harvest candidates (biggest losses first)

### Updating Positions

After buying/selling, re-export from Fidelity and regenerate:
```bash
# Your workflow to update mystocks.txt and mypositions.csv
# from the Fidelity Portfolio_Positions export
```

**Note:** The cost basis P&L is your ACTUAL gain/loss. The signal P&L (entry price from signature) shows performance since the signal triggered - these may differ if you bought before/after the signal.

## Project Structure

```
/your-projects/
├── psar-backtesting/        ← This project
│   ├── bt.py                 # Main CLI
│   ├── config.py             # Configuration
│   ├── signatures.py         # Signature management
│   ├── positions.py          # Portfolio positions (cost basis)
│   ├── prices.py             # Price fetching with market timing
│   ├── file_parser.py        # Parse V2 scanner HTML output
│   ├── scanner_bridge.py     # Call scanner for sell detection
│   ├── html_report.py        # Pretty HTML report generation
│   └── data/
│       ├── signatures.json   # All signatures with positions
│       ├── runs/             # Stored scanner outputs
│       └── reports/          # Generated HTML reports
│
└── market-psar-scanner/     ← Scanner (sibling directory)
    └── data/
        ├── mystocks.txt      # Your portfolio tickers
        └── mypositions.csv   # Cost basis from Fidelity export
```

## Quick Start

```bash
# Create virtual environment
cd psar-backtesting
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Process a scanner output file
python bt.py process scanner_output.html --mode strong

# List all signatures with P/L
python bt.py signatures

# View detailed report
python bt.py report 20251212

# Generate pretty HTML reports
python bt.py html

# Open in browser
open data/reports/index.html
```

## Commands

### Command Summary

| Command | Calls Scanner? | Modifies Data? | Fetches Prices? |
|---------|----------------|----------------|-----------------|
| `process` | No | Yes (creates signature) | Yes (entry prices) |
| `signatures` | No | No | No |
| `report` | No | No | Yes (current prices) |
| `html` | No | No | Yes (current prices) |
| `check-sells` | **Yes*** | **Yes (closes positions)** | Yes (exit prices) |
| `check-sells -f FILE` | No | **Yes (closes positions)** | Yes (exit prices) |
| `check-sells --preview` | No* | **No (displays only)** | Yes (current prices) |
| `live` | No | No | Yes (current prices) |
| `close` | No | Yes (closes position) | Yes (exit price) |
| `delete` | No | Yes (removes signature) | No |
| `show` | No | No | No |
| `reset` | No | Yes (clears all) | No |

*Use `--from-file` to avoid calling scanner (faster)  
*`--preview` also reads `mypositions.csv` for cost basis P&L

### `process` - Process Scanner File

```bash
# Process with all buy signals
python bt.py process output.html

# Strong Buy only
python bt.py process output.html --mode strong

# Early Buy only
python bt.py process output.html --mode early

# Dividend only
python bt.py process output.html --mode dividend
```

**What happens:**
1. File content + mode is hashed
2. If hash exists → returns existing signature with stored data
3. If new → creates signature, fetches entry prices based on market timing
4. Stores original file for reference

### `signatures` - List All Signatures

```bash
python bt.py signatures
python bt.py signatures --mode strong
python bt.py signatures --limit 50
```

**Shows:**
```
📋 SIGNATURES (15)
====================================================================================================
ID                           Date         Mode     Open   Closed   Realized   Unrealized   Total     
----------------------------------------------------------------------------------------------------
20251212_163045_a1b2c3d4     2025-12-12   strong   8      4        +5.2%      +3.1%        +8.3%     
20251211_093015_e5f6g7h8     2025-12-11   all      12     2        +2.1%      +1.8%        +3.9%     
```

### `report` - Detailed Signature Report

```bash
python bt.py report 20251212
python bt.py report 20251212_163045  # More specific
```

**Shows:**
- Full signature details (date, source file, market status)
- All open positions with entry/current prices and P/L
- All closed positions with entry/exit prices and P/L
- Totals and statistics

### `html` - Generate HTML Reports

```bash
# Generate all reports + index
python bt.py html

# Generate single report
python bt.py html 20251212

# Custom output directory
python bt.py html -o ~/Desktop/reports
```

**What it does:**
1. Loads all signatures from `signatures.json`
2. Fetches **current prices** via yfinance for all open positions
3. Calculates P/L (entry price vs current price)
4. Generates pretty HTML reports

**Does NOT:**
- Call the scanner
- Automatically close positions
- Modify any data

**Creates:**
- `data/reports/index.html` - Clickable grid of all signatures
- `data/reports/report_<signature>.html` - Individual detailed reports

Reports feature:
- Dark theme, mobile-responsive
- Summary cards (Total P/L, Realized, Unrealized, Win Rate)
- Open positions table with live P/L
- Closed positions with entry/exit details
- Shareable standalone HTML files

### `check-sells` - Detect Sells

```bash
# Preview sells with P&L from cost basis (RECOMMENDED)
python bt.py check-sells --preview -f mystocks.html

# Call scanner live (slow - downloads data for all tickers)
python bt.py check-sells

# Use existing scanner output file (fast)
python bt.py check-sells --from-file scan.html
```

**Options:**
| Flag | Description |
|------|-------------|
| `-p, --preview` | Show sells with P&L but DON'T auto-close. Uses cost basis from mypositions.csv |
| `-f, --from-file FILE` | Parse existing scanner HTML instead of calling scanner (much faster) |

**Preview Mode Output:**
```
🔍 Reviewing positions for sell signals...
   📊 Loaded 232 positions from mypositions.csv
   Found 8 in Sell zone

======================================================================
🔴 SELL SIGNALS - Review Before Acting
======================================================================

Ticker   Signal Date  Signal $   Cost Basis   Current $  P&L %      Action
--------------------------------------------------------------------------------
MSTR     2024-10-20   $346.88    $84,526      $176.45    🔴 -49.1%  TAX LOSS?
NVDA     2024-11-15   $184.35    $249,068     $175.02    🔴 -5.1%   TAX LOSS?
AMD      2024-11-10   $221.12    $99,926      $210.78    🟠 -4.7%   Small loss
--------------------------------------------------------------------------------

📊 Summary:
   3 positions at a LOSS (tax loss harvest candidates)
   0 positions at a GAIN (take profit candidates)
```

**What it does:**
1. Gets all open positions across ALL signatures
2. Finds which tickers are in Sell zone:
   - **Without `--from-file`:** Calls your scanner (slow, needs to download data)
   - **With `--from-file`:** Parses existing file (fast, uses recent scan)
3. **With `--preview`:** Shows P&L using cost basis from mypositions.csv, sorted by loss (tax loss candidates first)
4. **Without `--preview`:** Fetches exit prices, closes positions, records P/L, updates signatures.json

**Recommended workflow:** 
```bash
# 1. Run scanner
cd ~/Dev/Python/Investing/market-psar-scanner
python main.py -mystocks --html mystocks.html --no-email

# 2. Preview sells with actual P&L (from cost basis)
cd ~/Dev/Python/Investing/psar-backtesting
python bt.py check-sells --preview -f ../market-psar-scanner/mystocks.html

# 3. Decide which to close, then close individually
python bt.py close MSTR
```

### `delete` - Delete a Signature

```bash
# Preview what will be deleted
python bt.py delete 20251212_094154

# Actually delete it
python bt.py delete 20251212_094154 --confirm
```

Removes the signature and its stored output file. Partial signature IDs work.

### `live` - Real-Time P/L

```bash
python bt.py live
```

Shows current quotes and P/L for all open positions across all signatures.

### `close` - Manual Close

```bash
# Close in all signatures
python bt.py close NVDA

# Close in specific signature
python bt.py close NVDA --signature 20251212

# Close at specific price
python bt.py close NVDA --price 142.50
```

### `show` - View Stored Output

```bash
python bt.py show 20251212
```

Shows the original scanner output that was stored when the signature was created.

### `reset` - Clear All Data

```bash
python bt.py reset --confirm
```

## Workflow Examples

### Daily Tracking

```bash
# Morning: Process today's scan (creates signature with entry prices)
python bt.py process morning_scan.html --mode strong

# During day: Check live P/L (just fetches current prices, no changes)
python bt.py live

# Evening: Preview sells with cost basis P&L (RECOMMENDED)
python bt.py check-sells --preview -f ../market-psar-scanner/mystocks.html

# Review the output, then close specific positions
python bt.py close MSTR  # Tax loss harvest
python bt.py close NVDA  # Take profit

# Or auto-close all sells (without --preview)
python bt.py check-sells -f ../market-psar-scanner/mystocks.html

# Generate shareable reports (fetches current prices, renders HTML)
python bt.py html
open data/reports/index.html
```

**Tip:** Always use `--preview` first to see P&L from your actual cost basis before closing positions. This helps identify tax loss harvest opportunities.

### Compare Modes

```bash
# Process same scan with different modes
python bt.py process scan.html --mode strong
python bt.py process scan.html --mode early

# Each creates separate signature
python bt.py signatures
```

### Weekly Review

```bash
# Generate all HTML reports
python bt.py html

# Open index in browser
open data/reports/index.html

# Click any signature card to see detailed report
```

### Share Results

```bash
# Generate reports to desktop
python bt.py html -o ~/Desktop/backtest-reports

# Zip and share
cd ~/Desktop
zip -r backtest-reports.zip backtest-reports/
```

## Trading Modes

| Mode | Flag | What's Tracked |
|------|------|----------------|
| Strong Buy | `-m strong` | PRSI bullish + Price > PSAR ≤5 days |
| Early Buy | `-m early` | PRSI bullish + Price < PSAR |
| All | `-m all` | Both Strong and Early |
| Dividend | `-m dividend` | Yield ≥2% in buy zones |

## Supported Scanner Format

Parses V2 scanner HTML with:
- Section headers: `<tr class='th-strongbuy'>`, `<tr class='th-earlybuy'>`, etc.
- Ticker format: `<td><strong>TICKER</strong></td>`
- CSS classes: `section-strongbuy`, `section-earlybuy`, `section-dividend`, `section-sell`

## Configuration

Edit `config.py`:

```python
# Scanner location (default: sibling directory)
SCANNER_DIR = Path('../market-psar-scanner')

# Or set environment variable
export SCANNER_DIR=/path/to/scanner
```

## Data Storage

```
psar-backtesting/
└── data/
    ├── signatures.json          # All signatures with positions
    ├── runs/                    # Stored scanner outputs by date
    │   └── 20251212/
    │       └── 20251212_163045_abc123.txt
    └── reports/                 # Generated HTML reports
        ├── index.html
        └── report_20251212_163045_abc123.html

market-psar-scanner/
└── data/
    ├── mystocks.txt             # Your portfolio tickers (one per line)
    └── mypositions.csv          # Cost basis from Fidelity export
```

### mypositions.csv Format

```csv
Symbol,Value,CostBasis,NumAccounts
NVDA,275689.75,292645.12,2
MSTR,42996.98,84525.81,1
AMD,96377.25,101048.25,1
FBTC,1478966.17,1282234.69,3
```

| Column | Description |
|--------|-------------|
| Symbol | Stock ticker |
| Value | Current market value (from Fidelity) |
| CostBasis | Total cost basis (what you paid) |
| NumAccounts | How many accounts hold this position |

**Note:** Value is the snapshot at export time. The backtester uses CostBasis for P&L calculations with live prices.

## Requirements

```
yfinance>=0.2.36
pandas>=2.0.0
pytz>=2024.1
beautifulsoup4>=4.12.0
```

## License

MIT
