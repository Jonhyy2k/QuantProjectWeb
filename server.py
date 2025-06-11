import os
import json
import re
import secrets
import threading
import time
import traceback
import multiprocessing
from datetime import datetime, timedelta
import requests
import schedule
import yfinance as yf
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from newsapi import NewsApiClient
import shutil
import matplotlib
matplotlib.use('Agg') # Use a non-interactive backend for server environments

# Custom Module Imports (ensure these .py files are in the same directory)
from mainall import perform_analysis_for_server as run_stock_analysis
from Inputs_Cur import populate_valuation_model as run_inputs_cur_analysis, field_map, field_cell_map
from AssetPlotter import plot_assets_with_highlights, ASSET_MAP

# ==============================================================================
# App Initialization and Configuration
# ==============================================================================

app = Flask(__name__)

# --- Primary Configuration ---
app.secret_key = os.environ.get('SECRET_KEY', 'a-strong-default-secret-key-for-development')

# For AWS, set this environment variable to your PostgreSQL or MySQL database URL.
# Example: "postgresql://user:password@host:port/dbname"
db_uri = os.environ.get('DATABASE_URL', 'sqlite:///stock_analysis_local.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['NEWS_API_KEY'] = os.environ.get('NEWS_API_KEY', '178e06846327414aa7440357aeabcb3e')

# Initialize extensions
db = SQLAlchemy(app)
newsapi = NewsApiClient(api_key=app.config['NEWS_API_KEY'])

# --- Constants & File Paths ---
PUSHOVER_USER_KEY = os.environ.get('PUSHOVER_USER_KEY', "uyy9e7ihn6r3u8yxmzw64btrqwv7gx")
PUSHOVER_API_TOKEN = os.environ.get('PUSHOVER_API_TOKEN', "am486b2ntgarapn4yc3ieaeyg5w6gd")
TXT_FILE = "STOCK_ANALYSIS_RESULTS.txt"
MAGNIFICENT_SEVEN = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
GENERAL_MARKET_KEYWORDS = ["stock market", "finance", "economic outlook", "market trends", "investing", "S&P 500", "NASDAQ", "Dow Jones"]
CURRENCY_ANALYSIS_DIR = os.path.join(app.static_folder, 'currency_analyses_outputs')
os.makedirs(CURRENCY_ANALYSIS_DIR, exist_ok=True)


# ==============================================================================
# SQLAlchemy Database Models
# ==============================================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    analyses = db.relationship('Analysis', backref='user', lazy=True, cascade="all, delete-orphan")
    watchlists = db.relationship('Watchlist', backref='user', lazy=True, cascade="all, delete-orphan")

class Analysis(db.Model):
    __tablename__ = 'analyses'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_action = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'symbol', name='_user_symbol_uc'),)


# ==============================================================================
# Helper Functions (News, Data Extraction, Notifications)
# ==============================================================================

def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

def format_news_query(keywords_list):
    return " OR ".join(f'"{keyword}"' for keyword in keywords_list)

def fetch_articles(query_string, page_size=20, language='en', sort_by='publishedAt'):
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
        top_headlines = newsapi.get_everything(
            q=query_string, language=language, sort_by=sort_by, page_size=page_size, from_param=from_date
        )
        if top_headlines.get('status') == 'ok':
            return [
                article for article in top_headlines.get('articles', [])
                if article.get('title') != "[Removed]" and article.get('description') and article.get('urlToImage')
            ]
        else:
            app.logger.error(f"NewsAPI error: {top_headlines.get('message')}")
            return []
    except Exception as e:
        app.logger.error(f"Exception during NewsAPI call: {e}")
        return []

def get_user_watchlist_tickers(user_id):
    watchlist_items = Watchlist.query.filter_by(user_id=user_id).all()
    return [item.symbol for item in watchlist_items]

def get_watchlist_news_articles(user_id):
    tickers = get_user_watchlist_tickers(user_id)
    if not tickers:
        return []
    query = format_news_query(tickers)
    return fetch_articles(query_string=query)

def get_general_market_news_articles():
    mag7_keywords = [f"{ticker} stock" for ticker in MAGNIFICENT_SEVEN]
    combined_keywords = mag7_keywords + GENERAL_MARKET_KEYWORDS
    query = format_news_query(combined_keywords)
    return fetch_articles(query_string=query, page_size=30)

def extract_data_from_block(analysis_block_text):
    extracted_data = {}
    if not analysis_block_text:
        return None

    symbol_match = re.search(r'=== ANALYSIS FOR ([\w.-]+) ===', analysis_block_text, re.IGNORECASE)
    if symbol_match:
        extracted_data['symbol'] = symbol_match.group(1).upper()
    else:
        return None

    rec_match = re.search(r'Recommendation:\s*(.*?)(?=\n\s*---|===|\Z)', analysis_block_text, re.DOTALL | re.IGNORECASE)
    extracted_data['recommendation'] = ' '.join(rec_match.group(1).strip().split()) if rec_match else 'N/A'

    sigma_match = re.search(r'Sigma Score:\s*([+-]?[\d.]+)', analysis_block_text, re.IGNORECASE)
    extracted_data['sigma'] = float(sigma_match.group(1)) if sigma_match else None

    price_match = re.search(r'Current Price:\s*\$?([+-]?[\d.]+)', analysis_block_text, re.IGNORECASE)
    extracted_data['price'] = float(price_match.group(1)) if price_match else None

    change_match = re.search(r'Change:\s*([+-]?[\d.]+)\s*\(([-+]?[\d.]+)%?\)', analysis_block_text, re.IGNORECASE)
    if change_match:
        extracted_data['daily_change_absolute'] = float(change_match.group(1))
        extracted_data['daily_change_percent'] = float(change_match.group(2))
    else:
        extracted_data['daily_change_absolute'] = 0.0
        extracted_data['daily_change_percent'] = 0.0

    predictions = {}
    prediction_section_match = re.search(r'=== PRICE PREDICTIONS ===(.*?)(?===|\Z)', analysis_block_text, re.DOTALL | re.IGNORECASE)
    if prediction_section_match:
        prediction_text = prediction_section_match.group(1)
        target_30d_match = re.search(r'30-Day Target:\s*\$?([+-]?[\d.]+)\s*\(([-+]?[\d.]+)%\)', prediction_text, re.IGNORECASE)
        if target_30d_match:
            predictions['price_target_30d'] = float(target_30d_match.group(1))
            predictions['expected_return_30d'] = float(target_30d_match.group(2))
        target_60d_match = re.search(r'60-Day Target:\s*\$?([+-]?[\d.]+)\s*\(([-+]?[\d.]+)%\)', prediction_text, re.IGNORECASE)
        if target_60d_match:
            predictions['price_target_60d'] = float(target_60d_match.group(1))
            predictions['expected_return_60d'] = float(target_60d_match.group(2))
        plot_match = re.search(r'Prediction Plot:\s*(prediction_plots/[^\s]+)', prediction_text, re.IGNORECASE)
        if plot_match:
            predictions['plot_path'] = plot_match.group(1).strip()
            extracted_data['plot_path'] = predictions['plot_path']
    extracted_data['predictions'] = predictions

    risk_metrics = {}
    risk_section_match = re.search(r'=== RISK METRICS ===(.*?)(?===|\Z)', analysis_block_text, re.DOTALL | re.IGNORECASE)
    if risk_section_match:
        risk_text = risk_section_match.group(1)
        drawdown_match = re.search(r'Maximum Drawdown:\s*([+-]?[\d.]+)(%?)', risk_text, re.IGNORECASE)
        if drawdown_match:
            risk_metrics['max_drawdown'] = float(drawdown_match.group(1))
        sharpe_match = re.search(r'Sharpe Ratio:\s*([+-]?[\d.]+)', risk_text, re.IGNORECASE)
        if sharpe_match:
            risk_metrics['sharpe'] = float(sharpe_match.group(1))
        kelly_match = re.search(r'Kelly Criterion:\s*([+-]?[\d.]+)', risk_text, re.IGNORECASE)
        if kelly_match:
            risk_metrics['kelly'] = float(kelly_match.group(1))
        risk_level_match = re.search(r'Overall Risk Level:\s*(\w+)', risk_text, re.IGNORECASE)
        if risk_level_match:
            risk_metrics['risk_level'] = risk_level_match.group(1).title()
    extracted_data['risk_metrics'] = risk_metrics

    company_match = re.search(r'Company:\s*(.*)', analysis_block_text, re.IGNORECASE)
    if company_match:
        extracted_data['company_name'] = company_match.group(1).strip()

    news_sentiment_match = re.search(r'News Sentiment Score:\s*([+-]?[\d.]+)', analysis_block_text, re.IGNORECASE)
    if news_sentiment_match:
        extracted_data['news_sentiment_score'] = float(news_sentiment_match.group(1))

    return extracted_data

def find_most_recent_analysis_from_txt_and_sync_db(user_id, symbol):
    target_symbol_upper = symbol.upper()
    if not os.path.exists(TXT_FILE): return None, None, None
    try:
        with open(TXT_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        app.logger.error(f"Failed to read {TXT_FILE}: {e}")
        return None, None, None

    timestamp_match = re.search(r'Generated on:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', content)
    if not timestamp_match:
        app.logger.warning(f"Could not find 'Generated on:' timestamp in {TXT_FILE}.")
        return None, None, None
    
    file_timestamp_str = timestamp_match.group(1)
    timestamp_obj = datetime.strptime(file_timestamp_str, '%Y-%m-%d %H:%M:%S')
    
    analysis_data = extract_data_from_block(content)
    if not analysis_data or analysis_data.get('symbol') != target_symbol_upper:
        app.logger.warning(f"No valid analysis for {target_symbol_upper} found in {TXT_FILE}.")
        return None, None, None

    existing_analysis = Analysis.query.filter_by(user_id=user_id, symbol=target_symbol_upper, timestamp=timestamp_obj).first()
    if existing_analysis:
        app.logger.info(f"Found existing analysis in DB (ID: {existing_analysis.id})")
        return analysis_data, file_timestamp_str, existing_analysis.id
    
    try:
        new_analysis = Analysis(user_id=user_id, symbol=target_symbol_upper, analysis_data=json.dumps(analysis_data), timestamp=timestamp_obj)
        db.session.add(new_analysis)
        db.session.commit()
        app.logger.info(f"Inserted new analysis from {TXT_FILE} into DB (ID: {new_analysis.id})")
        return analysis_data, file_timestamp_str, new_analysis.id
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error syncing analysis for {target_symbol_upper}: {e}")
        return None, None, None

def send_pushover_notification(username, title, message):
    if not all([PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY]): return
    try:
        payload = {"token": PUSHOVER_API_TOKEN, "user": PUSHOVER_USER_KEY, "title": f"StockPulse - {username}", "message": message}
        requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=10)
    except Exception as e:
        app.logger.error(f"Pushover notification failed: {e}")

def run_analysis_in_process(user_id, symbol):
    return run_stock_analysis(user_id=user_id, symbol=symbol)

# ==============================================================================
# Templating Helpers
# ==============================================================================

@app.template_filter('datetimeformat')
def format_datetime_filter(value, format_str='%Y-%m-%d %H:%M'):
    if not value: return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
    if isinstance(value, datetime):
        return value.strftime(format_str)
    return value

@app.context_processor
def inject_global_vars():
    return {'now': datetime.utcnow()}

# ==============================================================================
# Core Routes (Auth, Dashboard)
# ==============================================================================

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    analyses = Analysis.query.filter_by(user_id=session['user_id']).order_by(Analysis.timestamp.desc()).all()
    watchlist = get_user_watchlist_tickers(session['user_id'])
    return render_template('index.html', analyses=analyses, watchlist=watchlist, username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session.permanent = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            return render_template('register.html', error="Username already exists")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==============================================================================
# Feature Routes (Analysis, News, Plotting)
# ==============================================================================

@app.route('/analyze', methods=['POST'])
@app.route('/analyze/new', methods=['POST'])
def analyze():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    symbol = request.form.get('symbol', '').strip().upper()
    if not symbol: return jsonify({'error': 'Invalid symbol'}), 400

    try:
        process = multiprocessing.Process(target=run_analysis_in_process, args=(session['user_id'], symbol))
        process.start()
        process.join()

        analysis_data, timestamp_str, analysis_id = find_most_recent_analysis_from_txt_and_sync_db(session['user_id'], symbol)

        if analysis_id:
            send_pushover_notification(session['username'], f"Analysis for {symbol} Completed", f"View your new analysis for {symbol} now.")
            return jsonify({'success': True, 'symbol': symbol, 'analysis_id': analysis_id})
        else:
            app.logger.error(f"Analysis for {symbol} ran, but failed to sync from TXT to DB.")
            return jsonify({'error': 'Analysis completed, but failed to save result.'}), 500
    except Exception as e:
        app.logger.error(f"Exception in /analyze route for {symbol}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/analysis/<int:analysis_id>')
def view_analysis(analysis_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    analysis = Analysis.query.filter_by(id=analysis_id, user_id=session['user_id']).first_or_404()
    analysis_data = json.loads(analysis.analysis_data)
    user_action = analysis.user_action

    if analysis_data.get('type') == 'Inputs_Cur_Analysis' or 'download_link' in analysis_data or 'excel_path' in analysis_data:
        excel_path = analysis_data.get('excel_path') or analysis_data.get('download_link')
        download_link = url_for('static', filename=excel_path.replace('\\', '/')) if excel_path else None
        return render_template('inputs_cur_form.html', success='Inputs Excel file ready for download.', download_link=download_link, analysis_id=analysis_id, username=session.get('username'))

    symbol = analysis_data.get('symbol') or analysis_data.get('target_asset') or 'N/A'
    plot_path = analysis_data.get('predictions', {}).get('plot_path') or analysis_data.get('plot_path')
    if plot_path: analysis_data['plot_path'] = plot_path

    news = []
    try:
        news_response = newsapi.get_everything(q=symbol, language='en', sort_by='publishedAt', page_size=10)
        if news_response.get('status') == 'ok':
            news = news_response.get('articles', [])
    except Exception:
        pass # Silently fail on news fetch for this view
    analysis_data['news'] = news

    return render_template('analysis.html', analysis=analysis_data, symbol=symbol, user_action=user_action, analysis_id=analysis_id)

@app.route('/news')
def news_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    watchlist_tickers = get_user_watchlist_tickers(session['user_id'])
    return render_template('news.html', username=session.get('username'), has_watchlist=bool(watchlist_tickers), watchlist=watchlist_tickers)

@app.route('/inputs_cur', methods=['GET', 'POST'])
def inputs_cur_page():
    if 'user_id' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        if not request.form.get('csrf_token') == session.get('csrf_token'):
            return render_template('inputs_cur_form.html', error="CSRF token validation failed.", username=session.get('username'))
        
        ticker_symbol = request.form.get('ticker_symbol', '').strip().upper()
        if not ticker_symbol:
            return render_template('inputs_cur_form.html', error="Ticker symbol cannot be empty.", username=session.get('username'))

        try:
            template_path = "LIS_Valuation_Empty.xlsx"
            output_dir = os.path.join(app.static_folder, 'currency_analyses_outputs')
            os.makedirs(output_dir, exist_ok=True)
            safe_ticker_filename = ticker_symbol.replace(" ", "_").replace("/", "_")
            output_file_name = f"{safe_ticker_filename}_Valuation_Model_{time.strftime('%d%m%Y_%H%M')}.xlsx"
            final_output_path = os.path.join(output_dir, output_file_name)

            run_inputs_cur_analysis(template_path, final_output_path, ticker_symbol, field_map, field_cell_map)

            if os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 0:
                relative_excel_path = os.path.relpath(final_output_path, app.static_folder).replace("\\", "/")
                download_link = url_for('static', filename=relative_excel_path)
                return render_template('inputs_cur_form.html', success=f"Analysis for {ticker_symbol} completed!", download_link=download_link, username=session.get('username'))
            else:
                return render_template('inputs_cur_form.html', error="Analysis failed to generate the Excel file.", username=session.get('username'))
        except Exception as e:
            app.logger.error(f"Error during Inputs_Cur analysis: {e}", exc_info=True)
            return render_template('inputs_cur_form.html', error=f"An error occurred: {str(e)}", username=session.get('username'))
    
    return render_template('inputs_cur_form.html', username=session.get('username'))

@app.route('/asset_plotter', methods=['GET', 'POST'])
def asset_plotter_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        if not request.form.get('csrf_token') == session.get('csrf_token'):
            return jsonify({'error': 'CSRF token validation failed'}), 400
        try:
            target_asset = request.form.get('target_asset', '').strip().upper()
            related_assets_str = request.form.get('related_assets', '').strip()
            start_date = request.form.get('start_date', '').strip()
            end_date = request.form.get('end_date', '').strip()
            ma_window = int(request.form.get('ma_window', 20))
            average_related = 'average_related' in request.form

            if not all([target_asset, start_date, end_date]):
                return render_template('asset_plotter_form.html', error="Target asset, start date, and end date are required.", username=session.get('username'))
            
            related_assets = [ASSET_MAP.get(a.lower(), a) for a in related_assets_str.split(',') if a.strip()]
            target_asset_mapped = ASSET_MAP.get(target_asset.lower(), target_asset)
            
            events = {date: desc for date, desc in zip(request.form.getlist('event_dates[]'), request.form.getlist('event_descriptions[]')) if date and desc}

            asset_plots_dir = os.path.join(app.static_folder, 'asset_plots')
            os.makedirs(asset_plots_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"asset_plot_{target_asset_mapped}_{timestamp}.png"
            output_path = os.path.join(asset_plots_dir, output_filename)

            plot_assets_with_highlights(target_asset_mapped, related_assets, start_date, end_date, events or None, average_related, ma_window)

            default_output = "bloomberg_style_asset_performance.png"
            if os.path.exists(default_output):
                shutil.move(default_output, output_path)
                plot_url = url_for('static', filename=f'asset_plots/{output_filename}')
                
                plot_data = {"type": "Asset_Plotter", "target_asset": target_asset_mapped, "related_assets": related_assets, "start_date": start_date, "end_date": end_date, "ma_window": ma_window, "average_related": average_related, "events": events, "plot_file": f'asset_plots/{output_filename}'}
                new_plot_analysis = Analysis(user_id=session['user_id'], symbol=target_asset_mapped, analysis_data=json.dumps(plot_data), user_action="Asset Plot Generated")
                db.session.add(new_plot_analysis)
                db.session.commit()

                return render_template('asset_plotter_form.html', success="Chart generated successfully!", plot_url=plot_url, username=session.get('username'))
            else:
                return render_template('asset_plotter_form.html', error="Failed to generate chart.", username=session.get('username'))

        except Exception as e:
            app.logger.error(f"Error in asset plotter: {e}", exc_info=True)
            return render_template('asset_plotter_form.html', error=f"An error occurred: {str(e)}", username=session.get('username'))

    return render_template('asset_plotter_form.html', username=session.get('username'))

# ==============================================================================
# API and AJAX Routes
# ==============================================================================

@app.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    symbol = request.form.get('symbol', '').strip().upper()
    if not symbol: return jsonify({'error': 'Invalid symbol'}), 400
    try:
        new_item = Watchlist(user_id=session['user_id'], symbol=symbol)
        db.session.add(new_item)
        db.session.commit()
        return jsonify({'success': True, 'symbol': symbol})
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Symbol already in watchlist'}), 400

@app.route('/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    symbol = request.form.get('symbol', '').strip().upper()
    if not symbol: return jsonify({'error': 'Invalid symbol'}), 400
    item = Watchlist.query.filter_by(user_id=session['user_id'], symbol=symbol).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True, 'symbol': symbol})
    return jsonify({'error': 'Symbol not found in watchlist'}), 404

@app.route('/analysis/delete', methods=['POST'])
def delete_analysis():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    analysis_id = request.form.get('analysis_id')
    analysis = Analysis.query.filter_by(id=analysis_id, user_id=session['user_id']).first()
    if analysis:
        symbol = analysis.symbol
        db.session.delete(analysis)
        db.session.commit()
        return jsonify({'success': True, 'analysis_id': analysis_id, 'symbol': symbol})
    return jsonify({'error': 'Analysis not found or access denied'}), 404

@app.route('/api/news_articles')
def api_news_articles():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    news_type = request.args.get('type', 'general')
    user_id = session['user_id']
    articles = []
    if news_type == 'watchlist':
        if get_user_watchlist_tickers(user_id):
            articles = get_watchlist_news_articles(user_id)
        else: # Fallback to general if watchlist is empty
            articles = get_general_market_news_articles()
    else:
        articles = get_general_market_news_articles()
    return jsonify(articles=articles)

@app.route('/api/stock-prices', methods=['POST'])
def get_stock_prices():
    if 'user_id' not in session: return jsonify({'error': 'Not logged in'}), 401
    symbols = request.form.getlist('symbols[]')
    if not symbols: return jsonify({'error': 'No symbols provided'}), 400
    
    prices = {}
    try:
        symbols_str = ' '.join([s.strip().upper() for s in symbols if s.strip()])
        tickers_data = yf.Tickers(symbols_str)
        for symbol in symbols:
            ticker_info = tickers_data.tickers.get(symbol.upper())
            if ticker_info:
                hist = ticker_info.history(period="2d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                    change_abs = current_price - prev_close
                    change_percent = (change_abs / prev_close * 100) if prev_close else 0
                    prices[symbol] = {'price': float(current_price), 'change_absolute': float(change_abs), 'change_percent': float(change_percent)}
    except Exception as e:
        app.logger.error(f"yfinance failed to fetch prices: {e}")

    return jsonify({'success': True, 'prices': prices})

# ==============================================================================
# Main Execution
# ==============================================================================
if __name__ == "__main__":
    # For production, use a WSGI server like Gunicorn.
    # Example: gunicorn --bind 0.0.0.0:8000 server:app
    app.run(host='127.0.0.1', port=5000, debug=True)
