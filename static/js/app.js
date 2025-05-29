// Configuration
const CONFIG = {
    api: {
        stockPrices: '/api/stock-prices',
        analyze: '/analyze',
        analyzeNew: '/analyze/new',
        watchlistAdd: '/watchlist/add',
        watchlistRemove: '/watchlist/remove',
        setAction: '/action',
        share: '/share/',
        deleteAnalysis: '/analysis/delete'
    },
    refreshInterval: 30000, // Price refresh interval in ms
    toastDelay: 4000,      // Toast auto-hide delay in ms
    debounceDelay: 300     // Debounce delay for AJAX calls
};

// Cache for jQuery selectors to improve performance
const SELECTORS = {};

// Helper function to debounce function calls
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// Helper function to get CSRF token
function getCSRFToken() {
    return $('meta[name="csrf-token"]').attr('content') || '';
}

$(document).ready(function() {
    // Cache frequently used selectors
    SELECTORS.themeToggle = $('#theme-toggle');
    SELECTORS.themeLightIcon = $('.theme-light-icon');
    SELECTORS.themeDarkIcon = $('.theme-dark-icon');
    SELECTORS.toastContainer = $('#toast-container');
    SELECTORS.priceDisplays = $('.price-display, .current-price');
    SELECTORS.tickerItems = $('.ticker-item');
    
    // Initialize theme based on saved preference
    initTheme();

    // Theme toggling functionality
    SELECTORS.themeToggle.on('click', function() {
        toggleTheme();
    });

    // Function to initialize theme
    function initTheme() {
        try {
            const savedTheme = localStorage.getItem('theme') || 'light';
            if (savedTheme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
                SELECTORS.themeLightIcon.addClass('d-none');
                SELECTORS.themeDarkIcon.removeClass('d-none');
            } else {
                document.documentElement.setAttribute('data-theme', 'light');
                SELECTORS.themeLightIcon.removeClass('d-none');
                SELECTORS.themeDarkIcon.addClass('d-none');
            }
        } catch (e) {
            console.error('Error accessing localStorage:', e);
            // Fallback to light theme if localStorage is not available
            document.documentElement.setAttribute('data-theme', 'light');
            SELECTORS.themeLightIcon.removeClass('d-none');
            SELECTORS.themeDarkIcon.addClass('d-none');
        }
    }

    // Function to toggle theme
    function toggleTheme() {
        try {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            if (newTheme === 'dark') {
                SELECTORS.themeLightIcon.addClass('d-none');
                SELECTORS.themeDarkIcon.removeClass('d-none');
                showToast('Dark mode enabled', 'info');
            } else {
                SELECTORS.themeLightIcon.removeClass('d-none');
                SELECTORS.themeDarkIcon.addClass('d-none');
                showToast('Light mode enabled', 'info');
            }
        } catch (e) {
            console.error('Error accessing localStorage:', e);
            showToast('Theme preference could not be saved', 'warning');
        }
    }

    // Function to show toast notifications
    function showToast(message, type = 'info') {
        // Make sure toast container exists
        if (SELECTORS.toastContainer.length === 0) {
            $('body').append('<div id="toast-container" class="position-fixed bottom-0 end-0 p-3" style="z-index: 1056"></div>');
            SELECTORS.toastContainer = $('#toast-container');
        }
        
        // Set appropriate icon based on type
        let iconClass = 'fas fa-info-circle';
        if (type === 'success') iconClass = 'fas fa-check-circle';
        if (type === 'danger') iconClass = 'fas fa-exclamation-triangle';
        if (type === 'warning') iconClass = 'fas fa-exclamation-circle';

        const toastId = 'toast-' + Date.now();
        const toast = $(`
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="${iconClass} me-2"></i> ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `);
        
        SELECTORS.toastContainer.append(toast);
        
        // Check if Bootstrap is loaded
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            try {
                const toastElement = document.getElementById(toastId);
                const bsToast = new bootstrap.Toast(toastElement, { 
                    autohide: true, 
                    delay: CONFIG.toastDelay 
                });
                bsToast.show();
                
                // Cleanup on hide
                toastElement.addEventListener('hidden.bs.toast', function() {
                    $(this).remove();
                });
                
                // Fallback cleanup in case the event doesn't fire
                setTimeout(function() {
                    if ($('#' + toastId).length > 0) {
                        $('#' + toastId).remove();
                    }
                }, CONFIG.toastDelay + 1000);
            } catch (e) {
                console.error('Error showing toast:', e);
                // Fallback if Bootstrap Toast fails
                toast.fadeIn().delay(CONFIG.toastDelay).fadeOut(function() {
                    $(this).remove();
                });
            }
        } else {
            // Fallback if Bootstrap is not available
            console.warn('Bootstrap Toast not available, using fallback');
            toast.fadeIn().delay(CONFIG.toastDelay).fadeOut(function() {
                $(this).remove();
            });
        }
    }

    // Function to update dashboard counts
    function updateCounts() {
        // Cache selectors for performance
        const analysesTable = $('#analyses-table');
        const buyCountElement = $('#buy-count');
        const sellCountElement = $('#sell-count');
        const analysisCountElement = $('#analysis-count');
        const watchlistCountElement = $('#watchlist-count');
        const watchlistContainer = $('#watchlist-container');
        
        // Only proceed if these elements exist
        if (analysesTable.length === 0) return;
        
        let buyCount = 0;
        let sellCount = 0;
        
        analysesTable.find('tbody tr').each(function() {
            const actionBadge = $(this).find('.action-badge');
            if (actionBadge.hasClass('buy') || actionBadge.hasClass('strong_buy')) {
                buyCount++;
            } else if (actionBadge.hasClass('sell') || actionBadge.hasClass('strong_sell')) {
                sellCount++;
            }
        });
        
        // Update the count displays
        if (buyCountElement.length) buyCountElement.text(buyCount);
        if (sellCountElement.length) sellCountElement.text(sellCount);
        if (analysisCountElement.length) analysisCountElement.text(analysesTable.find('tbody tr').length);
        if (watchlistCountElement.length && watchlistContainer.length) {
            watchlistCountElement.text(watchlistContainer.find('li:not(#empty-watchlist)').length);
        }
    }

    // Function to fetch current prices 
    const loadStockPrices = debounce(function() {
        const symbolsToFetch = new Set();
         
        // Get all elements that need price updates
        SELECTORS.priceDisplays = $('.price-display, .current-price');
        SELECTORS.tickerItems = $('.ticker-item');
        
        // Collect all symbols to fetch
        SELECTORS.priceDisplays.each(function() {
            const symbol = $(this).data('symbol');
            if(symbol) symbolsToFetch.add(symbol);
        });
        
        SELECTORS.tickerItems.each(function() {
            const symbol = $(this).data('symbol') || $(this).find('.ticker-symbol').text();
            if(symbol) symbolsToFetch.add(symbol);
        });

        if (symbolsToFetch.size === 0) return;

        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        // Fetch prices from the API
        $.ajax({
            url: CONFIG.api.stockPrices,
            method: 'POST',
            data: { symbols: Array.from(symbolsToFetch) },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    updatePriceDisplays(response.prices);
                    console.log("Price update complete with real data.");
                } else {
                    console.error("Failed to fetch prices:", response.error);
                    // Show "N/A" instead of random prices
                    showUnavailablePrices(symbolsToFetch);
                }
            },
            error: function(xhr) {
                console.error("Error fetching prices:", xhr);
                // Show "N/A" instead of random prices
                showUnavailablePrices(symbolsToFetch);
            }
        });
    }, CONFIG.debounceDelay);
    
    // Function to update price displays with fetched data
    function updatePriceDisplays(fetchedPrices) {
        // Update price displays
        SELECTORS.priceDisplays.each(function() {
            const element = $(this);
            const symbol = element.data('symbol');
            
            if (fetchedPrices[symbol]) {
                const currentPrice = parseFloat(fetchedPrices[symbol].price);
                if (!isNaN(currentPrice)) {
                    element.text('$' + currentPrice.toFixed(2)).removeClass('text-muted');

                    // Handle profit/loss display
                    if (element.hasClass('current-price')) {
                        const row = element.closest('tr');
                        const plCell = row.find('.profit-loss');
                        // If we had entry prices, we could calculate P/L
                        plCell.text('--.--%').addClass('text-muted');
                    }
                } else {
                    element.text('$?.??').addClass('text-muted');
                }
            } else {
                // No data available for this symbol
                element.text('$?.??').addClass('text-muted');
                
                // Handle profit/loss display
                if (element.hasClass('current-price')) {
                    const row = element.closest('tr');
                    const plCell = row.find('.profit-loss');
                    plCell.text('--.--%').addClass('text-muted');
                }
            }
        });
        
        // Update ticker tape
        SELECTORS.tickerItems.each(function() {
            const element = $(this);
            const symbol = element.find('.ticker-symbol').text();
            
            if (fetchedPrices[symbol]) {
                const priceData = fetchedPrices[symbol];
                const priceElement = element.find('.ticker-price');
                const changeElement = element.find('.ticker-change');
                
                // Update price
                priceElement.text('$' + parseFloat(priceData.price).toFixed(2));
                
                // Update change percentage
                const changePercent = parseFloat(priceData.change_percent);
                const changeText = (changePercent >= 0 ? '+' : '') + changePercent.toFixed(2) + '%';
                changeElement.text(changeText);
                
                // Update class
                changeElement.removeClass('positive negative').addClass(changePercent >= 0 ? 'positive' : 'negative');
            } else {
                // No data available, show placeholder
                const priceElement = element.find('.ticker-price');
                const changeElement = element.find('.ticker-change');
                
                priceElement.text('$?.??');
                changeElement.text('--.--%');
                changeElement.removeClass('positive negative');
            }
        });
        
        console.log("[INFO] Updated price displays with real-time data");
    }
    
    // Fallback function to show unavailable prices when API fails
    function showUnavailablePrices(symbolsToFetch) {
        console.log("Using N/A for unavailable prices for:", Array.from(symbolsToFetch));
        
        // Update price displays with N/A
        SELECTORS.priceDisplays.each(function() {
            const element = $(this);
            element.text('N/A').addClass('text-muted');
            
            // Handle profit/loss display
            if (element.hasClass('current-price')) {
                const row = element.closest('tr');
                const plCell = row.find('.profit-loss');
                plCell.text('N/A').addClass('text-muted');
            }
        });
        
        // Update ticker tape
        SELECTORS.tickerItems.each(function() {
            const element = $(this);
            const priceElement = element.find('.ticker-price');
            const changeElement = element.find('.ticker-change');
            
            // Update price and change
            priceElement.text('N/A');
            changeElement.text('N/A');
            
            // Remove positive/negative classes
            changeElement.removeClass('positive negative');
        });
    }


    // Analyze stock form submission
    $('#analyze-form').on('submit', function(e) {
        e.preventDefault();
        
        // Get and validate the symbol
        const symbolInput = $('#symbol');
        const symbol = symbolInput.val().toUpperCase().trim();
        const form = $(this);
        const button = form.find('button[type="submit"]');
        const originalButtonHtml = button.html();

        // Validate symbol
        if (!symbol) {
            showToast('Please enter a stock symbol.', 'warning');
            symbolInput.focus();
            return;
        }
        
        // Simple symbol validation (customize based on your requirements)
        const symbolPattern = /^[A-Z0-9.-]{1,10}$/;
        if (!symbolPattern.test(symbol)) {
            showToast('Invalid symbol format. Please enter a valid stock symbol.', 'warning');
            symbolInput.focus();
            return;
        }

        // Show loading state
        button.html('<span class="spinner-border spinner-border-sm me-2"></span>Analyzing...').prop('disabled', true);

        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        // Make the AJAX request
        $.ajax({
            url: CONFIG.api.analyze,
            method: 'POST',
            data: { symbol: symbol },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.has_recent) {
                    // Using confirm() for simplicity
                    const confirmMsg = `A recent analysis for ${symbol} was found (dated ${response.timestamp}). Request a new one?`;
                    
                    if (confirm(confirmMsg)) {
                        requestNewAnalysis(symbol, button, originalButtonHtml, symbolInput);
                    } else {
                        // Use existing analysis
                        button.html(originalButtonHtml).prop('disabled', false);
                        window.location.href = `/analysis/${response.analysis_id}`;
                    }
                } else if (response.success) {
                    showToast(`Analysis started for ${response.symbol}. You'll be notified.`, 'success');
                    symbolInput.val('');
                    button.html(originalButtonHtml).prop('disabled', false);
                } else {
                    showToast(response.error || 'Unknown error during analysis request.', 'danger');
                    button.html(originalButtonHtml).prop('disabled', false);
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to analyze stock:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Error communicating with server.';
                showToast(errorMsg, 'danger');
                button.html(originalButtonHtml).prop('disabled', false);
            }
        });
    });
    
    // Function to request a new analysis
    function requestNewAnalysis(symbol, button, originalButtonHtml, symbolInput) {
        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
        
        $.ajax({
            url: CONFIG.api.analyzeNew,
            method: 'POST',
            data: { symbol: symbol },
            headers: headers,
            dataType: 'json',
            success: function(newResponse) {
                if (newResponse.success) {
                    showToast(`New analysis started for ${newResponse.symbol}. You'll be notified.`, 'success');
                    symbolInput.val('');
                } else {
                    showToast(newResponse.error || 'Error starting new analysis.', 'danger');
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to start new analysis:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Server error starting new analysis.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                button.html(originalButtonHtml).prop('disabled', false);
            }
        });
    }


    // Watchlist management
    // Add to watchlist (delegated event)
    $('body').on('click', '.add-watchlist', function() {
        const symbol = $(this).data('symbol');
        const button = $(this);
        const originalHtml = button.html();

        // Validate symbol
        if (!symbol) {
            showToast('Invalid symbol', 'warning');
            return;
        }

        // Show loading state
        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);

        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        // Make the AJAX request
        $.ajax({
            url: CONFIG.api.watchlistAdd,
            method: 'POST',
            data: { symbol: symbol },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    showToast(`${symbol} added to watchlist!`, 'success');
                    updateWatchlistButtonsAdd(button, symbol);
                    updateWatchlistContainer(symbol);
                    updateCounts();
                } else {
                    showToast(response.error || `Failed to add ${symbol} to watchlist.`, 'danger');
                    button.html(originalHtml);
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to add to watchlist:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Server error adding to watchlist.';
                showToast(errorMsg, 'danger');
                button.html(originalHtml);
            },
            complete: function() {
                button.prop('disabled', false);
            }
        });
    });

    // Remove from watchlist (delegated event)
    $('body').on('click', '.remove-watchlist, .remove-watchlist-alt', function() {
        const symbol = $(this).data('symbol');
        const button = $(this);
        const originalHtml = button.html();
        
        // Validate symbol
        if (!symbol) {
            showToast('Invalid symbol', 'warning');
            return;
        }

        // Show loading state
        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);

        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        // Make the AJAX request
        $.ajax({
            url: CONFIG.api.watchlistRemove,
            method: 'POST',
            data: { symbol: symbol },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    showToast(`${symbol} removed from watchlist.`, 'info');
                    updateWatchlistButtonsRemove(button, symbol);
                    removeFromWatchlistContainer(symbol);
                    updateCounts();
                } else {
                    showToast(response.error || `Failed to remove ${symbol}.`, 'danger');
                    button.html(originalHtml);
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to remove from watchlist:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Server error removing from watchlist.';
                showToast(errorMsg, 'danger');
                button.html(originalHtml);
            },
            complete: function() {
                button.prop('disabled', false);
            }
        });
    });
    
    // Helper function to update buttons when adding to watchlist
    function updateWatchlistButtonsAdd(clickedButton, symbol) {
        const isAnalysisPageButton = clickedButton.closest('.stock-header').length > 0;
        
        if(isAnalysisPageButton) { 
            // For analysis page, we have a specific pair of add/remove buttons
            // Hide the add button
            clickedButton.addClass('d-none');
            // Show the remove button
            $('.remove-watchlist[data-symbol="' + symbol + '"]').removeClass('d-none');
        } else {
            // For other pages (like dashboard table), transform the button
            clickedButton
                .removeClass('add-watchlist btn-outline-success btn-outline-warning')
                .addClass('remove-watchlist-alt btn-outline-danger')
                .html('<i class="fas fa-times"></i>')
                .attr('title', 'Remove from Watchlist');
                
            // Update any other add buttons for this symbol
            $(`.add-watchlist[data-symbol='${symbol}']`).not(clickedButton).addClass('d-none');
            $(`.remove-watchlist-alt[data-symbol='${symbol}']`).not(clickedButton).removeClass('d-none');
        }
        
        // Make sure analysis page buttons are correctly synced
        if (!isAnalysisPageButton) {
            // If we're not on the analysis page but there are analysis page buttons
            $(`.add-watchlist[data-symbol='${symbol}']`).addClass('d-none');
            $(`.remove-watchlist[data-symbol='${symbol}']`).removeClass('d-none');
        }
    }
    
    // Helper function to update buttons when removing from watchlist
    function updateWatchlistButtonsRemove(clickedButton, symbol) {
        const isAnalysisPageButton = clickedButton.closest('.stock-header').length > 0;
        
        if(isAnalysisPageButton) {
            // For analysis page, we have a specific pair of add/remove buttons
            // Hide the remove button
            clickedButton.addClass('d-none');
            // Show the add button
            $('.add-watchlist[data-symbol="' + symbol + '"]').removeClass('d-none');
        } else {
            // For other pages (like dashboard table), transform the button
            clickedButton
                .removeClass('remove-watchlist remove-watchlist-alt btn-warning btn-outline-danger')
                .addClass('add-watchlist btn-outline-success')
                .html('<i class="fas fa-star"></i>')
                .attr('title', 'Add to Watchlist');
                
            // Update any other remove buttons for this symbol
            $(`.remove-watchlist-alt[data-symbol='${symbol}']`).not(clickedButton).addClass('d-none');
            $(`.add-watchlist[data-symbol='${symbol}']`).not(clickedButton).removeClass('d-none');
        }
        
        // Make sure analysis page buttons are correctly synced
        if (!isAnalysisPageButton) {
            // If we're not on the analysis page but there are analysis page buttons
            $(`.remove-watchlist[data-symbol='${symbol}']`).addClass('d-none'); 
            $(`.add-watchlist[data-symbol='${symbol}']`).removeClass('d-none');
        }
    }
    
    // Helper function to add to watchlist container
    function updateWatchlistContainer(symbol) {
        const watchlistContainer = $('#watchlist-container');
        
        // Only proceed if watchlist container exists
        if (watchlistContainer.length > 0) {
            // Check if symbol already exists in watchlist
            if (watchlistContainer.find('li').filter(function() { 
                return $(this).find('.fw-bold').text() === symbol; 
            }).length === 0) {
                // Create new watchlist item
                const newItem = $(`
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div><span class="fw-bold">${symbol}</span><span class="price-display ms-2 small text-muted" data-symbol="${symbol}">$--.--</span></div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary quick-analyze" data-symbol="${symbol}" title="Quick Analyze"><i class="fas fa-chart-line"></i></button>
                            <button class="btn btn-sm btn-outline-danger remove-watchlist" data-symbol="${symbol}" title="Remove from Watchlist"><i class="fas fa-times"></i></button>
                        </div>
                    </li>
                `);
                
                // Hide empty watchlist message
                $('#empty-watchlist').hide();
                
                // Add to watchlist
                watchlistContainer.append(newItem);
                
                // Update prices
                loadStockPrices();
            }
        }
    }
    
    // Helper function to remove from watchlist container
    function removeFromWatchlistContainer(symbol) {
        const watchlistContainer = $('#watchlist-container');
        const emptyWatchlist = $('#empty-watchlist');
        
        if (watchlistContainer.length > 0) {
            // Find and remove the watchlist item
            watchlistContainer.find('li').filter(function() { 
                return $(this).find('.fw-bold').text() === symbol; 
            }).fadeOut(300, function() {
                $(this).remove();
                
                // Show empty message if no items left
                if (watchlistContainer.find('li:not(#empty-watchlist)').length === 0 && emptyWatchlist.length > 0) {
                    emptyWatchlist.show();
                }
            });
        }
    }


    // Initialize action buttons on page load for analysis page
    const initActionButtons = function() {
        // Only initialize if action buttons exist
        if ($('.set-action').length > 0) {
            // Set up action buttons
            $('.set-action').on('click', handleActionButtonClick);
        }
    };
    
    // Set Buy/Sell action handler
    function handleActionButtonClick() {
        const button = $(this);
        const action = button.data('action');
        const analysis_id = button.data('id');
        const originalHtml = button.html();
        const actionButtons = $('.set-action');

        // Validate analysis_id
        if (!analysis_id) {
            console.error("Analysis ID not found for set-action button.");
            showToast("Cannot set action: Analysis ID missing.", "danger");
            return; // Prevent AJAX call if ID is missing
        }

        // Show loading state for all action buttons
        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);
        actionButtons.not(button).prop('disabled', true);

        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        // Make the AJAX request
        $.ajax({
            url: CONFIG.api.setAction,
            method: 'POST',
            data: { analysis_id: analysis_id, action: action },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    // Format the action text nicely
                    const actionText = action.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                    showToast(`Action set to ${actionText}.`, 'success');

                    // Update UI elements
                    updateActionButtonStatus(button, actionText);
                } else {
                    showToast(response.error || 'Failed to set action.', 'danger');
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to set action:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Server error setting action.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                // Restore button states
                button.html(originalHtml);
                actionButtons.prop('disabled', false);
            }
        });
    }
    
    // Helper function to update UI after action is set
    function updateActionButtonStatus(activeButton, actionText) {
        // Update button class to show active state
        $('.set-action').removeClass('active');
        activeButton.addClass('active');

        // Update status badge
        const statusBadge = $('#action-status .badge');
        if (statusBadge.length) {
            statusBadge
                .text(`Current Action: ${actionText}`)
                .removeClass('bg-secondary bg-info')
                .addClass('bg-info');
        }
    }

    // Share analysis handler (delegated event)
    $('body').on('click', '.share-analysis', function() {
        const id = $(this).data('id');
        const button = $(this);
        
        // Validate ID
        if (!id) {
            showToast("Missing analysis ID", "warning");
            return;
        }
        
        // Show loading state
        const originalIcon = button.find('i').attr('class');
        button.find('i').removeClass().addClass('fas fa-spinner fa-spin');

        // Make the AJAX request
        $.ajax({
            url: CONFIG.api.share + id,
            method: 'GET',
            dataType: 'json',
            success: function(response) {
                if (response.share_url) {
                    // Set link in input field
                    const shareLinkInput = $('#share-link');
                    if (shareLinkInput.length) {
                        shareLinkInput.val(response.share_url);
                    
                        // Update modal title if needed
                        const shareModalLabel = $('#shareModalLabel');
                        if (shareModalLabel.length) {
                            shareModalLabel.text(`Share Analysis (ID: ${id})`);
                        }
                    
                        // Show modal if Bootstrap is available
                        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                            try {
                                const shareModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('shareModal'));
                                if (shareModal) {
                                    shareModal.show();
                                } else {
                                    throw new Error('Modal instance not created');
                                }
                            } catch (e) {
                                console.error('Error showing modal:', e);
                                showToast('Share URL: ' + response.share_url, 'success');
                            }
                        } else {
                            // Fallback if Bootstrap is not available
                            console.warn('Bootstrap Modal not available');
                            showToast('Share URL: ' + response.share_url, 'success');
                        }
                    } else {
                        showToast('Share URL: ' + response.share_url, 'success');
                    }
                } else {
                    showToast(response.error || 'Could not retrieve share link.', 'warning');
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to get share link:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Error retrieving share link.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                button.find('i').removeClass().addClass(originalIcon);
            }
        });
    });
    
    // Delete analysis handler (delegated event)
    $('body').on('click', '.delete-analysis', function() {
        const id = $(this).data('id');
        const button = $(this);
        const row = button.closest('tr');
        
        // Validate ID
        if (!id) {
            showToast("Missing analysis ID", "warning");
            return;
        }
        
        // Confirm deletion
        if (!confirm('Are you sure you want to delete this analysis? This action cannot be undone.')) {
            return;
        }
        
        // Show loading state
        const originalIcon = button.find('i').attr('class');
        button.find('i').removeClass().addClass('fas fa-spinner fa-spin');
        button.prop('disabled', true);

        // Prepare CSRF token if available
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
        
        // Make the AJAX request
        $.ajax({
            url: CONFIG.api.deleteAnalysis,
            method: 'POST',
            data: { analysis_id: id },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    // Remove the row with animation
                    row.fadeOut(300, function() {
                        $(this).remove();
                        
                        // Update counts after removal
                        updateCounts();
                        
                        // Check if table is now empty
                        if ($('#analyses-table tbody tr').length === 0) {
                            // Show empty message by replacing table with message
                            const emptyMessage = `
                                <div class="text-center text-muted p-5" id="empty-analyses">
                                    <i class="fas fa-folder-open fa-3x mb-3"></i>
                                    <p class="mb-1">No analyses performed yet.</p>
                                    <p class="small mb-0">Use the analysis form above to get started.</p>
                                </div>
                            `;
                            
                            $('#analyses-table').closest('.table-responsive').replaceWith(emptyMessage);
                        }
                    });
                    
                    showToast(`Analysis for ${response.symbol} deleted successfully`, 'success');
                } else {
                    showToast(response.error || 'Failed to delete analysis', 'danger');
                    button.find('i').removeClass().addClass(originalIcon);
                    button.prop('disabled', false);
                }
            },
            error: function(xhr) {
                console.error('[ERROR] Failed to delete analysis:', xhr);
                const errorMsg = xhr.responseJSON?.error || 'Server error deleting analysis.';
                showToast(errorMsg, 'danger');
                button.find('i').removeClass().addClass(originalIcon);
                button.prop('disabled', false);
            }
        });
    });

    // Copy share link button inside modal
    $('#copy-link').on('click', function() {
        const copyText = document.getElementById('share-link');
        const button = $(this);
        
        if (!copyText || !copyText.value) {
            showToast('No link to copy', 'warning');
            return;
        }
        
        // Try to copy to clipboard
        try {
            if (navigator.clipboard && window.isSecureContext) {
                // Use modern Clipboard API if available and in secure context
                navigator.clipboard.writeText(copyText.value)
                    .then(() => {
                        const originalText = button.html();
                        button.html('<i class="fas fa-check me-1"></i> Copied!');
                        setTimeout(() => { button.html(originalText); }, 2500);
                    })
                    .catch(err => {
                        console.error('Clipboard API error:', err);
                        fallbackCopyTextToClipboard(copyText);
                    });
            } else {
                // Use fallback for older browsers
                fallbackCopyTextToClipboard(copyText);
            }
        } catch (err) {
            showToast('Failed to copy link.', 'warning');
            console.error('Copy error:', err);
        }
    });
    
    // Fallback copy function for older browsers
    function fallbackCopyTextToClipboard(copyText) {
        // Select the text
        copyText.select();
        copyText.setSelectionRange(0, 99999); // For mobile devices
        
        // Try to copy using document.execCommand (older method)
        try {
            const success = document.execCommand('copy');
            if (success) {
                showToast('Link copied to clipboard!', 'success');
            } else {
                showToast('Please press Ctrl+C to copy the link', 'info');
            }
        } catch (err) {
            showToast('Please press Ctrl+C to copy the link', 'info');
            console.error('execCommand error:', err);
        }
    }


    // Quick analyze from watchlist (delegated event)
    $('body').on('click', '.quick-analyze', function() {
        const symbol = $(this).data('symbol');
        if (symbol) {
            // Validate the symbol (simple check)
            if (/^[A-Z0-9.-]{1,10}$/.test(symbol)) {
                window.location.href = `/analysis/${symbol}`;
            } else {
                showToast('Invalid symbol format', 'warning');
            }
        } else {
            showToast('Missing symbol', 'warning');
        }
    });

    // Refresh data button (Dashboard)
    $('#refresh-data').on('click', function() {
        const button = $(this);
        
        // Show loading state
        button.html('<span class="spinner-border spinner-border-sm"></span> Refreshing...').prop('disabled', true);

        // Debounce the refresh to prevent multiple rapid clicks
        debounce(function() {
            // Refresh prices
            loadStockPrices();
            
            // Update counts based on current DOM
            updateCounts();
            
            // Restore button after a short delay
            setTimeout(function() {
                button.html('<i class="fas fa-sync-alt"></i> Refresh Data').prop('disabled', false);
                showToast('Display data refreshed!', 'success');
            }, 750);
        }, CONFIG.debounceDelay)();
    });
    
    // Initialize page-specific features
    function initPageFeatures() {
        // Initialize action buttons for analysis page
        initActionButtons();
        
        // Dashboard-specific initializations
        if ($('#analyses-table').length > 0) {
            updateCounts();
            loadStockPrices();
            
            // Optional: Set up auto-refresh interval for prices
            // const priceRefreshInterval = setInterval(loadStockPrices, CONFIG.refreshInterval);
        }
        
        // Initialize Bootstrap tooltips if available
        initTooltips();
    }
    
    // Initialize tooltips
    function initTooltips() {
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            try {
                const tooltipTriggerList = [].slice.call(
                    document.querySelectorAll('[data-bs-toggle="tooltip"], [title]:not(script)')
                );
                
                tooltipTriggerList.forEach(function(tooltipTriggerEl) {
                    if (!bootstrap.Tooltip.getInstance(tooltipTriggerEl)) {
                        new bootstrap.Tooltip(tooltipTriggerEl, {
                            boundary: document.body
                        });
                    }
                });
            } catch (e) {
                console.warn('Error initializing tooltips:', e);
            }
        }
    }
    
    // Run page initialization
    initPageFeatures();

});