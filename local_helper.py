# local_helper.py
# This script runs on the user's machine.
# python -m PyInstaller --onefile --windowed local_helper.py

import subprocess
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Allow requests from your web app's domain
CORS(app, resources={r"/run-analysis": {"origins": "http://51.21.79.94"}}) 

# The URL of your main web application on AWS
# IMPORTANT: This must be the actual URL of your server
BASE_SERVER_URL = "http://51.21.79.94" 

ANALYSIS_DIR = os.path.join(os.path.expanduser("~"), "QuantPulseAnalysis")

def run_local_analysis(ticker_symbol):
    """The core logic that was previously in the .bat file."""
    try:
        print(f"Received request to analyze: {ticker_symbol}")

        # 1. Create directory if it doesn't exist
        if not os.path.exists(ANALYSIS_DIR):
            os.makedirs(ANALYSIS_DIR)
        
        # 2. Download the necessary files from your main server
        print("Downloading analysis files...")
        # Download Inputs_Cur.py
        r_script = requests.get(f"{BASE_SERVER_URL}/static/Inputs_Cur.py")
        r_script.raise_for_status() # Will raise an error if download fails
        with open(os.path.join(ANALYSIS_DIR, "Inputs_Cur.py"), "wb") as f:
            f.write(r_script.content)

        # Download the Excel template
        r_excel = requests.get(f"{BASE_SERVER_URL}/static/LIS_Valuation_Empty.xlsx")
        r_excel.raise_for_status()
        with open(os.path.join(ANALYSIS_DIR, "LIS_Valuation_Empty.xlsx"), "wb") as f:
            f.write(r_excel.content)
            
        # 3. Pip install dependencies (only runs if needed)
        # Using "python -m pip" is more reliable
        print("Ensuring libraries are installed...")
        subprocess.run("python -m pip install openpyxl==3.1.5", check=True, shell=True)
        subprocess.run("python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple blpapi", check=True, shell=True)

        # 4. Run the analysis script
        # Using subprocess.run hides the "ugly" command window
        print(f"Running analysis for {ticker_symbol}...")
        # Note: We run the python script from within the target directory
        subprocess.run(
            f'python Inputs_Cur.py "{ticker_symbol}"',
            check=True,
            shell=True,
            cwd=ANALYSIS_DIR # Set the working directory
        )

        # 5. Clean up the Python script for security
        print("Cleaning up script file...")
        os.remove(os.path.join(ANALYSIS_DIR, "Inputs_Cur.py"))

        print("Analysis complete.")
        return True, "Analysis completed successfully."

    except Exception as e:
        print(f"An error occurred: {e}")
        return False, str(e)


@app.route('/run-analysis', methods=['POST'])
def handle_analysis_request():
    data = request.get_json()
    ticker = data.get('ticker')

    if not ticker:
        return jsonify({"status": "error", "message": "Ticker symbol is required."}), 400

    success, message = run_local_analysis(ticker)

    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message}), 500

if __name__ == '__main__':
    print("🚀 QuantPulse Local Helper is running.")
    print("This app must remain running to perform local Bloomberg analyses.")
    print("Listening on http://127.0.0.1:54321")
    app.run(host='127.0.0.1', port=54321)
