import blpapi
import time # Add time import if not already present

def get_normalized_news_sentiment(ticker_symbol):
    """
    Fetches and normalizes news sentiment for a given ticker from Bloomberg.
    Returns a sentiment score (0-1) or None if connection fails.
    """
    options = blpapi.SessionOptions()
    options.setServerHost("localhost")
    options.setServerPort(8194)
    session = blpapi.Session(options)

    try:
        print(f"[INFO] Attempting to connect to Bloomberg for {ticker_symbol} sentiment...")
        if not session.start():
            print("[WARNING] Failed to start Bloomberg session. Terminal might not be running.")
            return None # Return None if connection fails

        if not session.openService("//blp/refdata"):
            print("[WARNING] Failed to open Bloomberg reference data service.")
            session.stop()
            return None # Return None if service opening fails

        refDataService = session.getService("//blp/refdata")
        request = refDataService.createRequest("ReferenceDataRequest")

        # Use the passed ticker symbol
        request.getElement("securities").appendValue(f"{ticker_symbol} Equity") # Adapt as needed for non-US equities
        request.getElement("fields").appendValue("NEWS_SENTIMENT")

        session.sendRequest(request)

        sentiment_value = None
        start_time = time.time()
        timeout = 10 # seconds

        # Process events with timeout
        while time.time() - start_time < timeout:
            event = session.nextEvent(500) # Check for events every 500ms
            if event.eventType() == blpapi.Event.RESPONSE or event.eventType() == blpapi.Event.PARTIAL_RESPONSE:
                for msg in event:
                    securityData = msg.getElement("securityData")
                    for security in securityData.values():
                        fieldData = security.getElement("fieldData")
                        if fieldData.hasElement("NEWS_SENTIMENT"):
                            sentiment = fieldData.getElementAsFloat("NEWS_SENTIMENT")
                            # Normalize from -1 to 1 -> 0 to 1
                            sentiment_value = (sentiment + 1) / 2
                            print(f"[INFO] Retrieved Bloomberg sentiment {sentiment:.4f}, normalized to {sentiment_value:.4f}")
                            # Break inner loops once data is found
                            break
                    if sentiment_value is not None: break
                if sentiment_value is not None: break
            # Break if the session terminated or other terminal events occur
            elif event.eventType() in [blpapi.Event.SESSION_STATUS, blpapi.Event.SERVICE_STATUS]:
                # Check if session terminated
                 for msg in event:
                     if msg.messageType() == blpapi.Name("SessionTerminated"):
                         print("[WARNING] Bloomberg session terminated unexpectedly.")
                         return None # Or handle reconnection if desired
            elif event.eventType() == blpapi.Event.TIMEOUT:
                 print("[DEBUG] Bloomberg event timeout.")
                 continue # Continue waiting until overall timeout

            # Check if it's the final response event
            if event.eventType() == blpapi.Event.RESPONSE:
                break # Exit loop after final response

        if sentiment_value is None:
             print(f"[WARNING] Timeout or no sentiment data received for {ticker_symbol} within {timeout}s.")

        return sentiment_value

    except Exception as e:
        print(f"[ERROR] Error during Bloomberg API interaction for {ticker_symbol}: {e}")
        return None # Return None on any exception

    finally:
        # Ensure the session is stopped
        try:
            session.stop()
            print("[INFO] Bloomberg session stopped.")
        except Exception as e:
            print(f"[WARNING] Error stopping Bloomberg session: {e}")