from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash
import os
from mainall import perform_analysis_for_server as run_stock_analysis # Updated import
import requests
import schedule
import time
import threading
from datetime import datetime  # Import the datetime class
import multiprocessing
import re
import secrets  # For generating CSRF tokens
import yfinance as yf  # For fetching real-time stock prices
import traceback
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory 
from datetime import datetime
import os
import json
from Inputs_Cur import populate_valuation_model as run_inputs_cur_analysis # Rename for clarity

# ... rest of your Flask app code ...
app = Flask(__name__)
app.secret_key = "your_secret_key_here"
DB_FILE = "stock_analysis.db"
TXT_FILE = "STOCK_ANALYSIS_RESULTS.txt"

PUSHOVER_USER_KEY = "uyy9e7ihn6r3u8yxmzw64btrqwv7gx"
PUSHOVER_API_TOKEN = "am486b2ntgarapn4yc3ieaeyg5w6gd"

# CSRF Protection
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token


# In server.py, outside any function (global or app config)
CURRENCY_ANALYSIS_DIR = os.path.join(app.static_folder, 'currency_analyses_outputs')
os.makedirs(CURRENCY_ANALYSIS_DIR, exist_ok=True)

# In server.py

@app.route('/inputs_cur', methods=['GET', 'POST'])
def inputs_cur_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if not request.form.get('csrf_token') == session.get('csrf_token'):
            return jsonify({'error': 'CSRF token validation failed'}), 400

        ticker_symbol = request.form.get('ticker_symbol', '').strip().upper()
        if not ticker_symbol:
            return render_template('inputs_cur_form.html', error="Ticker symbol cannot be empty.", username=session.get('username'))

        try:
            # Define the template path (ensure LIS_Valuation_Empty.xlsx is accessible)
            template_path = "LIS_Valuation_Empty.xlsx" # Adjust path if necessary

            # Run the analysis from Inputs_Cur.py
            # The output_directory should be where Flask can serve files from, or you implement a download handler
            generated_excel_path = run_inputs_cur_analysis(
                template_path=template_path,
                output_directory=CURRENCY_ANALYSIS_DIR,
                ticker_symbol_from_web=ticker_symbol
            )

            if generated_excel_path:
                # Make the file path relative to the static folder for URL generation
                relative_excel_path = os.path.join('currency_analyses_outputs', os.path.basename(generated_excel_path))

                # Save metadata to the database
                conn = get_db_connection()
                cursor = conn.cursor()
                analysis_data_json = json.dumps({
                    "type": "Inputs_Cur_Analysis",
                    "ticker": ticker_symbol,
                    "output_file_relative": relative_excel_path, # Store relative path
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                timestamp_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO analyses (user_id, symbol, analysis_data, timestamp, user_action)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session['user_id'], ticker_symbol, analysis_data_json, timestamp_now, "Inputs_Cur Generated"))
                conn.commit()
                new_analysis_id = cursor.lastrowid
                conn.close()

                return render_template('inputs_cur_form.html',
                                       success=f"Analysis for {ticker_symbol} completed!",
                                       download_link=url_for('static', filename=relative_excel_path),
                                       analysis_id=new_analysis_id,
                                       username=session.get('username'))
            else:
                return render_template('inputs_cur_form.html', error="Analysis failed to generate the Excel file.", username=session.get('username'))

        except FileNotFoundError as fnf_error:
            app.logger.error(f"Template file not found: {fnf_error}")
            return render_template('inputs_cur_form.html', error=f"Critical error: Valuation template file not found.", username=session.get('username'))
        except Exception as e:
            app.logger.error(f"Error during Inputs_Cur analysis for {ticker_symbol}: {e}")
            traceback.print_exc() # For detailed error logging in Flask console
            return render_template('inputs_cur_form.html', error=f"An error occurred: {str(e)}", username=session.get('username'))

    return render_template('inputs_cur_form.html', username=session.get('username'))

# --- Add this filter definition ---
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    """Formats a datetime object or a string into a desired string format."""
    if value is None:
        return "N/A" # Or return an empty string ""

    # Try converting if it's a string (adjust parsing formats if needed)
    if isinstance(value, str):
        try:
            # Attempt ISO format first (common in databases/APIs)
            # Handle potential 'Z' timezone indicator
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            try:
                 # Add other formats your app might use
                 value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                  # If parsing fails, return the original string
                  return value

    # Format if it's a datetime object
    if isinstance(value, datetime):
        return value.strftime(format)

    # Otherwise, return the value as is
    return value

app.jinja_env.filters['datetimeformat'] = format_datetime

@app.context_processor
def inject_now():
  """Injects the current UTC datetime into the template context."""
  return {'now': datetime.utcnow()}

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def extract_data_from_block(analysis_block_text):
    """
    Extracts specific metrics from a single analysis block text.

    Args:
        analysis_block_text (str): The text content of one analysis block.

    Returns:
        dict: A dictionary containing the extracted values, or None if essential fields are missing.
    """
    extracted_data = {}
    if not analysis_block_text: # Handle empty input
        return None

    # --- Extract Basic Info ---
    symbol_match = re.search(r'=== ANALYSIS FOR ([\w.-]+) ===', analysis_block_text, re.IGNORECASE)
    if symbol_match:
        extracted_data['symbol'] = symbol_match.group(1).upper() # Ensure uppercase
    else:
        return None # Cannot proceed without symbol

    rec_match = re.search(r'Recommendation:\s*(.*?)(?=\n\s*---|===|\Z)', analysis_block_text, re.DOTALL | re.IGNORECASE)
    if rec_match:
        extracted_data['recommendation'] = ' '.join(rec_match.group(1).strip().split())
    else:
        extracted_data['recommendation'] = 'N/A' # Default if not found

    sigma_match = re.search(r'Sigma Score:\s*([+-]?[\d.]+)', analysis_block_text, re.IGNORECASE)
    if sigma_match:
        try:
            extracted_data['sigma'] = float(sigma_match.group(1)) # Match key used in original analysis.html
        except ValueError:
            extracted_data['sigma'] = None
    else:
        extracted_data['sigma'] = None

    price_match = re.search(r'Current Price:\s*\$?([+-]?[\d.]+)', analysis_block_text, re.IGNORECASE)
    if price_match:
         try:
            extracted_data['price'] = float(price_match.group(1))
         except ValueError:
            extracted_data['price'] = None
    else:
        extracted_data['price'] = None # Important for calculations

    # Add Change extraction if needed by frontend (matches analysis.html)
    change_match = re.search(r'Change:\s*([+-]?[\d.]+)\s*\(([-+]?[\d.]+)%?\)', analysis_block_text, re.IGNORECASE)
    if change_match:
        try:
            extracted_data['daily_change_absolute'] = float(change_match.group(1))
            extracted_data['daily_change_percent'] = float(change_match.group(2))
        except ValueError:
             extracted_data['daily_change_absolute'] = 0.0
             extracted_data['daily_change_percent'] = 0.0
    else:
         extracted_data['daily_change_absolute'] = 0.0
         extracted_data['daily_change_percent'] = 0.0

    # --- Extract Price Predictions ---
    predictions = {}
    # Check both possible section headers
    prediction_section_match = re.search(r'=== PRICE PREDICTIONS ===(.*?)(?===|\Z)', analysis_block_text, re.DOTALL | re.IGNORECASE)

    if prediction_section_match:
        prediction_text = prediction_section_match.group(1)
        target_30d_match = re.search(r'30-Day Target:\s*\$?([+-]?[\d.]+)\s*\(([-+]?[\d.]+)%\)', prediction_text, re.IGNORECASE)
        if target_30d_match:
            try:
                predictions['price_target_30d'] = float(target_30d_match.group(1))
                predictions['expected_return_30d'] = float(target_30d_match.group(2))
            except ValueError: pass
        target_60d_match = re.search(r'60-Day Target:\s*\$?([+-]?[\d.]+)\s*\(([-+]?[\d.]+)%\)', prediction_text, re.IGNORECASE)
        if target_60d_match:
             try:
                predictions['price_target_60d'] = float(target_60d_match.group(1))
                predictions['expected_return_60d'] = float(target_60d_match.group(2))
             except ValueError: pass
        plot_match = re.search(r'Prediction Plot:\s*(prediction_plots/[^\s]+)', prediction_text, re.IGNORECASE)
        if plot_match:
            # Get just the relative path from static/
            relative_plot_path = plot_match.group(1).strip()
            predictions['plot_path'] = relative_plot_path # Store the relative path
            # Also add to top level for compatibility if needed by analysis.html logic
            extracted_data['plot_path'] = relative_plot_path


    # If prediction section missing, maybe plot path is elsewhere? (Check main block)
    if 'plot_path' not in predictions:
         plot_match_main = re.search(r'Prediction Plot:\s*(prediction_plots/[^\s]+)', analysis_block_text, re.IGNORECASE)
         if plot_match_main:
             relative_plot_path = plot_match_main.group(1).strip()
             predictions['plot_path'] = relative_plot_path
             extracted_data['plot_path'] = relative_plot_path


    extracted_data['predictions'] = predictions

    # --- Extract Risk Metrics ---
    risk_metrics = {}
    risk_section_match = re.search(r'=== RISK METRICS ===(.*?)(?===|\Z)', analysis_block_text, re.DOTALL | re.IGNORECASE)

    if risk_section_match:
        risk_text = risk_section_match.group(1)
        drawdown_match = re.search(r'Maximum Drawdown:\s*([+-]?[\d.]+)(%?)', risk_text, re.IGNORECASE) # Capture % optionally
        if drawdown_match:
            try:
                 # Store as float, remove % sign if present
                 risk_metrics['max_drawdown'] = float(drawdown_match.group(1))
            except ValueError:
                 risk_metrics['max_drawdown'] = None
        sharpe_match = re.search(r'Sharpe Ratio:\s*([+-]?[\d.]+)', risk_text, re.IGNORECASE)
        if sharpe_match:
            try:
                risk_metrics['sharpe'] = float(sharpe_match.group(1)) # Match key used in analysis.html
            except ValueError: risk_metrics['sharpe'] = None
        kelly_match = re.search(r'Kelly Criterion:\s*([+-]?[\d.]+)', risk_text, re.IGNORECASE)
        if kelly_match:
             try:
                risk_metrics['kelly'] = float(kelly_match.group(1)) # Match key used in analysis.html
             except ValueError: risk_metrics['kelly'] = None

        # Add Risk Level if present (based on analysis.html structure)
        # Note: Risk Level is not in the txt file format spec or example txt file. Add regex if it exists.
        risk_level_match = re.search(r'Overall Risk Level:\s*(\w+)', risk_text, re.IGNORECASE) # Example pattern
        if risk_level_match:
            risk_metrics['risk_level'] = risk_level_match.group(1).title()

    extracted_data['risk_metrics'] = risk_metrics

    # Extract Company Name if available
    company_match = re.search(r'Company:\s*(.*)', analysis_block_text, re.IGNORECASE)
    if company_match:
        extracted_data['company_name'] = company_match.group(1).strip()

    # Extract News Sentiment if available
    news_sentiment_match = re.search(r'News Sentiment Score:\s*([+-]?[\d.]+)', analysis_block_text, re.IGNORECASE)
    if news_sentiment_match:
         try:
             extracted_data['news_sentiment_score'] = float(news_sentiment_match.group(1))
         except ValueError:
             extracted_data['news_sentiment_score'] = None


    return extracted_data

# --- REPLACE your existing find_most_recent_analysis_from_txt function with this ---
def find_most_recent_analysis_from_txt(user_id, symbol):
    """
    Search STOCK_ANALYSIS_RESULTS.txt for the most recent analysis for the given symbol.
    Extracts data from the block and checks the database.

    Returns a tuple of (analysis_data, timestamp_str, analysis_id) if found, else (None, None, None).
    """
    symbol_to_find = symbol.upper() # Ensure comparison is case-insensitive
    most_recent_block_text = None
    most_recent_timestamp_obj = None

    # --- Robust block finding logic ---
    if not os.path.exists(TXT_FILE):
        print(f"[INFO] {TXT_FILE} not found.")
        return None, None, None

    try:
        with open(TXT_FILE, 'r', encoding='utf-8') as f: # Specify encoding
            content = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read {TXT_FILE}: {e}")
        return None, None, None

    # Determine separator
    if "===== STOCK_ANALYSIS_RESULTS =====" in content:
        separator = "===== STOCK_ANALYSIS_RESULTS ====="
    elif "==================================================" in content:
        separator = "=================================================="
    else:
        separator = r'\n=== ANALYSIS FOR ' # Fallback

    # Split content
    if separator != r'\n=== ANALYSIS FOR ':
        blocks = content.split(separator)
    else:
        blocks = re.split(separator, content)[1:]
        blocks = ['=== ANALYSIS FOR ' + block for block in blocks]

    symbol_blocks_with_timestamps = []

    for block_idx, block in enumerate(blocks):
        if not block.strip(): continue

        block_symbol_match = re.search(r'=== ANALYSIS FOR ([\w.-]+) ===', block, re.IGNORECASE)
        if block_symbol_match and block_symbol_match.group(1).upper() == symbol_to_find:
            timestamp_str = None
            timestamp_obj = None

            ts_match_new = re.search(r'Generated on:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', block, re.IGNORECASE)
            if ts_match_new:
                timestamp_str = ts_match_new.group(1)
                try:
                    timestamp_obj = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print(f"[WARNING] Could not parse timestamp '{timestamp_str}' in block {block_idx} for {symbol_to_find}")
                    timestamp_obj = None

            # Add other potential timestamp formats here...

            if timestamp_obj:
                 # Reconstruct block text accurately
                 if separator != r'\n=== ANALYSIS FOR ':
                      reconstructed_block = separator + block if not block.startswith(separator) else block
                 else:
                      reconstructed_block = block
                 symbol_blocks_with_timestamps.append((reconstructed_block, timestamp_obj))
            else:
                # Attempt to use file modification time as a last resort timestamp
                try:
                    mtime = os.path.getmtime(TXT_FILE)
                    timestamp_obj = datetime.datetime.fromtimestamp(mtime)
                    print(f"[WARNING] Using file modification time {timestamp_obj} as fallback timestamp for block {block_idx} for {symbol_to_find}")
                    # Reconstruct block text accurately
                    if separator != r'\n=== ANALYSIS FOR ':
                        reconstructed_block = separator + block if not block.startswith(separator) else block
                    else:
                        reconstructed_block = block
                    symbol_blocks_with_timestamps.append((reconstructed_block, timestamp_obj))
                except Exception as e:
                    print(f"[ERROR] Could not get file modification time for {TXT_FILE}: {e}")
                    print(f"[WARNING] Skipping block {block_idx} for {symbol_to_find} due to missing timestamp.")


    if not symbol_blocks_with_timestamps:
        print(f"[INFO] No valid analysis blocks found for {symbol_to_find} in {TXT_FILE}.")
        return None, None, None

    # Sort by timestamp to find the most recent
    symbol_blocks_with_timestamps.sort(key=lambda x: x[1], reverse=True)
    most_recent_block_text, most_recent_timestamp_obj = symbol_blocks_with_timestamps[0]
    most_recent_timestamp_str = most_recent_timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[INFO] Found most recent block for {symbol_to_find} dated {most_recent_timestamp_str}")

    # --- Extract data from the most recent block ---
    analysis_data = extract_data_from_block(most_recent_block_text)

    if not analysis_data:
        print(f"[ERROR] Failed to extract data from the most recent block for {symbol_to_find}")
        return None, None, None

    # --- Check/Insert into Database (similar to original logic) ---
    conn = get_db_connection()
    cursor = conn.cursor()
    analysis_id = None
    try:
        cursor.execute('''
            SELECT id
            FROM analyses
            WHERE user_id = ? AND symbol = ? AND timestamp = ?
        ''', (user_id, symbol_to_find, most_recent_timestamp_str))
        existing = cursor.fetchone()

        if existing:
            analysis_id = existing['id']
            print(f"[INFO] Found existing analysis in DB (ID: {analysis_id}) for {symbol_to_find} at {most_recent_timestamp_str}")
        else:
            # Insert the newly extracted data if it wasn't in the DB for this timestamp
            analysis_json = json.dumps(analysis_data) # Use the extracted dictionary
            cursor.execute('''
                INSERT INTO analyses (user_id, symbol, analysis_data, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user_id, symbol_to_find, analysis_json, most_recent_timestamp_str))
            conn.commit()
            analysis_id = cursor.lastrowid # Get the ID of the newly inserted row
            print(f"[INFO] Inserted analysis from {TXT_FILE} into DB (ID: {analysis_id}) for {symbol_to_find} at {most_recent_timestamp_str}")

    except sqlite3.Error as e:
        print(f"[ERROR] Database error for {symbol_to_find}: {e}")
        conn.rollback() # Rollback any changes if error occurs
        return None, None, None # Return None on DB error
    finally:
        conn.close()

    # Return the extracted data, the timestamp string, and the analysis ID
    return analysis_data, most_recent_timestamp_str, analysis_id


def sync_data():
    print(f"[INFO] Running sync at {datetime.now()}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.id, a.user_id, a.symbol, u.username
            FROM analyses a
            JOIN users u ON a.user_id = u.id
            WHERE a.timestamp > datetime('now', '-6 hours')
        ''')
        recent_analyses = cursor.fetchall()
        
        for analysis in recent_analyses:
            send_pushover_notification(
                analysis['username'],
                f"New analysis completed for {analysis['symbol']}",
                f"View details: https://stockpulse.ngrok.app/analysis/{analysis['id']}"
            )
        
        conn.close()
        print("[INFO] Sync completed")
    except Exception as e:
        print(f"[ERROR] Sync failed: {e}")

def send_pushover_notification(username, title, message):
    try:
        payload = {
            "token": PUSHOVER_API_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "title": f"StockPulse - {username}",
            "message": message,
            "url": message if "http" in message else ""
        }
        response = requests.post("https://api.pushover.net/1/messages.json", data=payload)
        if response.status_code == 200:
            print(f"[INFO] Notification sent to {username}")
        else:
            print(f"[ERROR] Failed to send notification: {response.text}")
    except Exception as e:
        print(f"[ERROR] Notification error: {e}")

def run_scheduler():
    schedule.every(6).hours.do(sync_data)
    while True:
        schedule.run_pending()
        time.sleep(60)

scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

def run_analysis_in_process(user_id, symbol):
    return run_stock_analysis(user_id=user_id, symbol=symbol)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, symbol, timestamp, user_action
        FROM analyses
        WHERE user_id = ?
        ORDER BY timestamp DESC
    ''', (session['user_id'],))
    analyses = cursor.fetchall()
    
    cursor.execute('''
        SELECT symbol
        FROM watchlists
        WHERE user_id = ?
    ''', (session['user_id'],))
    watchlist = [row['symbol'] for row in cursor.fetchall()]
    
    conn.close()
    return render_template('index.html', analyses=analyses, watchlist=watchlist, username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            ''', (username, generate_password_hash(password)))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Username already exists")
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/analysis/<int:analysis_id>')
def view_analysis(analysis_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT analysis_data, user_action
        FROM analyses
        WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    analysis = cursor.fetchone()
    conn.close()
    
    if not analysis:
        return "Analysis not found or access denied", 404
    
    analysis_data = json.loads(analysis['analysis_data'])
    return render_template('analysis.html', analysis=analysis_data, symbol=analysis_data['symbol'], user_action=analysis['user_action'], analysis_id=analysis_id)

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    symbol = request.form['symbol'].strip().upper()
    if not symbol:
        return jsonify({'error': 'Invalid symbol'}), 400
    
    print(f"[DEBUG] User ID in /analyze: {session['user_id']}")
    analysis_data, timestamp, analysis_id = find_most_recent_analysis_from_txt(session['user_id'], symbol)
    
    if analysis_data and timestamp and analysis_id:
        return jsonify({
            'has_recent': True,
            'analysis_id': analysis_id,
            'timestamp': timestamp
        })
    
    try:
        process = multiprocessing.Process(target=run_analysis_in_process, args=(session['user_id'], symbol))
        process.start()
        process.join()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id
            FROM analyses
            WHERE user_id = ? AND symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (session['user_id'], symbol))
        new_analysis = cursor.fetchone()
        conn.close()
        
        if new_analysis:
            analysis_id = new_analysis['id']
            send_pushover_notification(
                session['username'],
                f"Analysis completed for {symbol}",
                f"View details: https://stockpulse.ngrok.app/analysis/{analysis_id}"
            )
            return jsonify({'success': True, 'symbol': symbol, 'analysis_id': analysis_id})
        else:
            return jsonify({'error': 'Analysis failed to save to database'}), 500
    except Exception as e:
        print(f"[ERROR] Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze/new', methods=['POST'])
def analyze_new():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    symbol = request.form['symbol'].strip().upper()
    if not symbol:
        return jsonify({'error': 'Invalid symbol'}), 400
    
    try:
        process = multiprocessing.Process(target=run_analysis_in_process, args=(session['user_id'], symbol))
        process.start()
        process.join()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id
            FROM analyses
            WHERE user_id = ? AND symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (session['user_id'], symbol))
        new_analysis = cursor.fetchone()
        conn.close()
        
        if new_analysis:
            analysis_id = new_analysis['id']
            send_pushover_notification(
                session['username'],
                f"Analysis completed for {symbol}",
                f"View details: https://stockpulse.ngrok.app/analysis/{analysis_id}"
            )
            return jsonify({'success': True, 'symbol': symbol, 'analysis_id': analysis_id})
        else:
            return jsonify({'error': 'Analysis failed to save to database'}), 500
    except Exception as e:
        print(f"[ERROR] Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/action', methods=['POST'])
def set_action():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    analysis_id = request.form['analysis_id']
    action = request.form['action']
    
    if action not in ['strong_buy', 'buy', 'sell', 'strong_sell']:
        return jsonify({'error': 'Invalid action'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE analyses
        SET user_action = ?
        WHERE id = ? AND user_id = ?
    ''', (action.replace('_', ' ').title(), analysis_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'action': action})

@app.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    symbol = request.form['symbol'].strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO watchlists (user_id, symbol)
            VALUES (?, ?)
        ''', (session['user_id'], symbol))
        conn.commit()
        return jsonify({'success': True, 'symbol': symbol})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Symbol already in watchlist'}), 400
    finally:
        conn.close()

@app.route('/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    symbol = request.form['symbol'].strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM watchlists
        WHERE user_id = ? AND symbol = ?
    ''', (session['user_id'], symbol))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'symbol': symbol})

@app.route('/analysis/delete', methods=['POST'])
def delete_analysis():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    analysis_id = request.form['analysis_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, check if the analysis belongs to the user
    cursor.execute('''
        SELECT id, symbol FROM analyses 
        WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    
    analysis = cursor.fetchone()
    if not analysis:
        conn.close()
        return jsonify({'error': 'Analysis not found or access denied'}), 404
    
    # If found and belongs to user, delete it
    cursor.execute('''
        DELETE FROM analyses
        WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'analysis_id': analysis_id, 'symbol': analysis['symbol']})

@app.route('/share/<int:analysis_id>')
def share_analysis(analysis_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    share_url = f"https://stockpulse.ngrok.app/analysis/{analysis_id}"
    return jsonify({'share_url': share_url})

@app.route('/api/stock-prices', methods=['POST'])
def get_stock_prices():
    """API endpoint to fetch real-time stock prices from Yahoo Finance"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    symbols = request.form.getlist('symbols[]')
    if not symbols and 'symbols' in request.form:
        # Handle case where symbols might be sent as a single comma-separated string
        symbols = request.form['symbols'].split(',')
    
    if not symbols:
        return jsonify({'error': 'No symbols provided'}), 400
    
    # Clean up symbols
    symbols = [s.strip().upper() for s in symbols if s.strip()]
    
    # Dictionary to store prices
    prices = {}
    
    try:
        # Create a single string of symbols for batch request
        symbols_str = ' '.join(symbols)
        
        # Fetch data for all symbols at once using yfinance
        # This is more efficient than fetching them individually
        print(f"[INFO] Fetching real-time data for: {symbols_str}")
        tickers_data = yf.Tickers(symbols_str)
        
        for symbol in symbols:
            try:
                # Get ticker data for this symbol
                ticker_info = tickers_data.tickers[symbol]
                
                # Get current price data
                ticker_history = ticker_info.history(period="2d")
                
                if not ticker_history.empty:
                    # Get today's and yesterday's close prices
                    if len(ticker_history) >= 2:
                        current_price = ticker_history['Close'].iloc[-1]
                        prev_close = ticker_history['Close'].iloc[-2]
                        
                        # Calculate change
                        change_abs = float(current_price - prev_close)
                        change_percent = float((change_abs / prev_close) * 100)
                    else:
                        # If only one day of data is available
                        current_price = ticker_history['Close'].iloc[-1]
                        change_abs = 0.0
                        change_percent = 0.0
                    
                    prices[symbol] = {
                        'price': float(current_price),
                        'change_absolute': change_abs,
                        'change_percent': change_percent
                    }
                    
                    print(f"[INFO] Fetched price for {symbol}: ${current_price:.2f} ({change_percent:.2f}%)")
                else:
                    # No data available
                    print(f"[WARNING] No price data found for {symbol}")
            except Exception as ticker_error:
                print(f"[ERROR] Error fetching data for {symbol}: {ticker_error}")
                # Continue with other symbols even if one fails
    
    except Exception as e:
        print(f"[ERROR] Failed to fetch stock prices: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
    # If we couldn't get any prices from Yahoo Finance, try using the cached data from the analysis file
    if not prices:
        print("[WARNING] No prices fetched from Yahoo Finance, falling back to cached data")
        try:
            prices = get_cached_prices_from_file(symbols)
        except Exception as cache_error:
            print(f"[ERROR] Failed to get cached prices: {cache_error}")
    
    return jsonify({
        'success': True,
        'prices': prices
    })

def get_cached_prices_from_file(symbols):
    """Fallback function to get cached prices from the analysis file"""
    prices = {}
    
    if os.path.exists(TXT_FILE):
        with open(TXT_FILE, 'r') as f:
            content = f.read()
        
        # Split by either old format or new format sections
        if '===== STOCK_ANALYSIS_RESULTS =====' in content:
            analysis_blocks = content.split('===== STOCK_ANALYSIS_RESULTS =====')
        else:
            analysis_blocks = content.split('==================================================')
        
        for symbol in symbols:
            # Try to find the most recent analysis for each symbol
            symbol_blocks = []
            
            for block in analysis_blocks:
                # Check both new and old format symbol headers
                symbol_match = re.search(r'=== ANALYSIS FOR (\w+) ===', block)
                
                if symbol_match and symbol_match.group(1).upper() == symbol:
                    # Try to extract timestamp if available (from newer format)
                    timestamp_match = re.search(r'Generated on: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', block)
                    timestamp = timestamp_match.group(1) if timestamp_match else None
                    
                    symbol_blocks.append((block, timestamp))
            
            if symbol_blocks:
                # Sort by timestamp if available, otherwise use the last one found
                if any(block[1] for block in symbol_blocks):
                    symbol_blocks = [block for block in symbol_blocks if block[1]]
                    symbol_blocks.sort(key=lambda x: x[1], reverse=True)
                
                # Use the most recent or last block
                most_recent_block = symbol_blocks[0][0]
                
                # Try both formats for price extraction
                price_match = re.search(r'Current Price: \$?([\d.]+)', most_recent_block)
                
                # Also try to find change data in both formats
                change_match = re.search(r'Change: ([+-]?[\d.]+) \(([-+]?[\d.]+)%\)', most_recent_block)
                
                if price_match:
                    price = float(price_match.group(1))
                    
                    # Default values
                    change_abs = 0.0
                    change_percent = 0.0
                    
                    if change_match:
                        try:
                            change_abs = float(change_match.group(1))
                            change_percent = float(change_match.group(2))
                        except (ValueError, IndexError):
                            # If there's an error parsing change values, keep defaults
                            pass
                    
                    prices[symbol] = {
                        'price': price,
                        'change_absolute': change_abs,
                        'change_percent': change_percent
                    }
                    
                    print(f"[INFO] Using cached price for {symbol}: ${price}")
    
    return prices

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)