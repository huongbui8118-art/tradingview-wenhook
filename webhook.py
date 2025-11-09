from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# TradeStation API credentials (from environment variables)
TS_API_KEY = os.environ.get('TS_API_KEY')
TS_API_SECRET = os.environ.get('TS_API_SECRET')
TS_ACCOUNT_ID = os.environ.get('TS_ACCOUNT_ID')
TS_API_URL = "https://api.tradestation.com/v3"
TS_AUTH_URL = "https://signin.tradestation.com/oauth/token"

# Cache for access token
access_token_cache = {
    'token': None,
    'expires_at': 0
}

def log(message):
    """Simple logging with timestamp"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def get_access_token():
    """Get TradeStation access token (with caching)"""
    try:
        # Check if cached token is still valid
        if access_token_cache['token'] and datetime.now().timestamp() < access_token_cache['expires_at']:
            return access_token_cache['token']
        
        log("Requesting new access token from TradeStation...")
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': TS_API_KEY,
            'client_secret': TS_API_SECRET
        }
        
        response = requests.post(TS_AUTH_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        access_token_cache['token'] = token_data.get('access_token')
        # Cache for 20 minutes (tokens usually valid for 30 min)
        access_token_cache['expires_at'] = datetime.now().timestamp() + 1200
        
        log("✅ Access token obtained successfully")
        return access_token_cache['token']
        
    except Exception as e:
        log(f"❌ Error getting access token: {str(e)}")
        raise

def place_order(symbol, action, quantity):
    """Place order on TradeStation"""
    try:
        token = get_access_token()
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Convert action to TradeStation format
        trade_action = "BUY" if action.lower() == "buy" else "SELL"
        
        order_data = {
            "AccountID": TS_ACCOUNT_ID,
            "Symbol": symbol,
            "Quantity": str(quantity),
            "OrderType": "Market",
            "TradeAction": trade_action,
            "TimeInForce": {
                "Duration": "DAY"
            }
        }
        
        log(f"📤 Placing {trade_action} order: {quantity} {symbol}")
        
        response = requests.post(
            f"{TS_API_URL}/orderexecution/orders",
            headers=headers,
            json=order_data
        )
        
        response.raise_for_status()
        result = response.json()
        
        log(f"✅ Order placed successfully: {result}")
        return result
        
    except Exception as e:
        log(f"❌ Error placing order: {str(e)}")
        raise

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint for TradingView alerts"""
    try:
        log("📨 Webhook received")
        
        # Get the raw data
        raw_data = request.get_data(as_text=True)
        log(f"Raw data: {raw_data}")
        
        # Try to parse as JSON first
        try:
            data = request.get_json()
            log(f"Parsed JSON: {data}")
        except:
            # If not JSON, try to parse key:value format
            log("Not JSON, trying key:value format...")
            data = raw_data
        
        # Parse the alert data
        if isinstance(data, str):
            # Handle "key: value; key: value" format
            parts = data.split(';')
            parsed = {}
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    parsed[key.strip()] = value.strip()
            
            symbol = parsed.get('symbol', 'BTCUSD')
            action = parsed.get('action', 'buy')
            quantity = float(parsed.get('amount', 10))
        else:
            # Handle JSON format
            symbol = data.get('ticker', data.get('symbol', 'BTCUSD'))
            action = data.get('action', 'buy')
            quantity = float(data.get('quantity', data.get('amount', 10)))
        
        log(f"Parsed order: {action.upper()} {quantity} {symbol}")
        
        # Validate inputs
        if not symbol or not action:
            raise ValueError("Missing required fields: symbol or action")
        
        # Place the order
        result = place_order(symbol, action, quantity)
        
        return jsonify({
            "status": "success",
            "message": f"{action.upper()} order placed for {quantity} {symbol}",
            "order": result
        }), 200
        
    except Exception as e:
        log(f"❌ Webhook error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "Webhook server is running"
    }), 200

@app.route('/', methods=['GET'])
def home():
    """Home page"""
    return """
    <html>
        <head><title>TradingView Webhook Server</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1>🚀 TradingView Webhook Server</h1>
            <p>Status: <strong style="color: green;">Running</strong></p>
            <p>Webhook endpoint: <code>/webhook</code></p>
            <p>Health check: <code>/health</code></p>
        </body>
    </html>
    """

if __name__ == '__main__':
    log("🚀 Starting webhook server...")
    
    # Validate environment variables
    if not TS_API_KEY or not TS_API_SECRET or not TS_ACCOUNT_ID:
        log("⚠️ WARNING: TradeStation credentials not set!")
        log("Please set TS_API_KEY, TS_API_SECRET, and TS_ACCOUNT_ID environment variables")
    else:
        log("✅ TradeStation credentials loaded")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
