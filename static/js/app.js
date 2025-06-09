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

    // ===================================================================
    // START: ALL THEME LOGIC MOVED INSIDE document.ready
    // ===================================================================

    // Function to initialize theme
    function initTheme() {
        try {
            // Default to 'light' if nothing is saved or accessible
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', savedTheme);

            if (savedTheme === 'dark') {
                SELECTORS.themeLightIcon.addClass('d-none');
                SELECTORS.themeDarkIcon.removeClass('d-none');
            } else {
                SELECTORS.themeLightIcon.removeClass('d-none');
                SELECTORS.themeDarkIcon.addClass('d-none');
            }
        } catch (e) {
            console.error('Error accessing localStorage for theme:', e);
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
            console.error('Error accessing localStorage for theme:', e);
            showToast('Theme preference could not be saved.', 'warning');
        }
    }
    
    // Initialize theme as soon as the DOM is ready
    initTheme();

    // Theme toggling functionality
    SELECTORS.themeToggle.on('click', function() {
        toggleTheme();
    });

    // ===================================================================
    // END: THEME LOGIC SECTION
    // ===================================================================


    $('#add-to-watchlist-direct-form').on('submit', function(e) {
        e.preventDefault();
        const tickerInput = $('#watchlist-ticker-input');
        const feedbackDiv = $('#watchlist-direct-feedback');
        const addButton = $('#add-watchlist-direct-btn');
        const originalButtonHtml = addButton.html();
        const symbol = tickerInput.val().trim().toUpperCase();

        if (!symbol) {
            feedbackDiv.text('Please enter a ticker symbol.').removeClass('text-success').addClass('text-danger alert alert-danger p-1 mt-1');
            setTimeout(() => feedbackDiv.text('').removeClass('alert alert-danger p-1 mt-1'), 3000);
            return;
        }

        addButton.html('<i class="fas fa-spinner fa-spin"></i> Adding...').prop('disabled', true);
        feedbackDiv.text('').removeClass('text-danger text-success alert alert-danger alert-success p-1 mt-1');

        $.ajax({
            url: CONFIG.api.watchlistAdd,
            method: 'POST',
            data: {
                symbol: symbol,
                csrf_token: getCSRFToken()
            },
            success: function(response) {
                if (response.success) {
                    showToast(`${symbol} added to watchlist.`, 'success');
                    tickerInput.val('');

                    if ($(`#watchlist-container li[data-watchlist-item="${symbol}"]`).length === 0) {
                        const newItemHtml = `
                            <li class="list-group-item d-flex justify-content-between align-items-center" data-watchlist-item="${symbol}">
                                <div>
                                    <span class="fw-bold me-2 watchlist-symbol-text">${symbol}</span>
                                    <span class="price-display small text-muted" data-symbol="${symbol}">$--.--</span>
                                </div>
                                <div class="btn-group btn-group-sm">
                                    <button class="btn btn-sm btn-outline-primary quick-analyze" data-symbol="${symbol}" title="Quick Analyze">
                                        <i class="fas fa-chart-line"></i>
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger remove-watchlist" data-symbol="${symbol}" title="Remove from Watchlist">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </div>
                            </li>`;
                        $('#watchlist-container').prepend(newItemHtml);
                        $('#empty-watchlist').addClass('d-none');

                        const countElement = $('#watchlist-count');
                        if (countElement.length) {
                            let currentCount = Number(countElement.text());
                            if (isNaN(currentCount)) currentCount = 0;
                            countElement.text(currentCount + 1);
                        }

                        $(`.add-watchlist[data-symbol="${symbol}"]`).addClass('d-none');
                        $(`.remove-watchlist-alt[data-symbol="${symbol}"]`).removeClass('d-none');

                        if (typeof fetchTickerTapePrices === 'function') {
                            fetchTickerTapePrices([symbol]);
                        } else if (typeof fetchWatchlistPrices === 'function') {
                            fetchWatchlistPrices([symbol]);
                        }
                    } else {
                        showToast(`${symbol} is already in your watchlist.`, 'info');
                    }
                } else {
                    showToast(response.error || `Failed to add ${symbol}. It might already be in your watchlist.`, 'danger');
                }
            },
            error: function(xhr) {
                const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'An error occurred.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                addButton.html(originalButtonHtml).prop('disabled', false);
            }
        });
    }); // End of #add-to-watchlist-direct-form submit handler

    function fetchWatchlistPrices(symbolsToFetch = []) {
        let symbols;
        if (symbolsToFetch.length > 0) {
            symbols = symbolsToFetch;
        } else {
            symbols = [];
            $('#watchlist-container .price-display').each(function() {
                symbols.push($(this).data('symbol'));
            });
        }

        if (symbols.length === 0) return;

        $.ajax({
            url: '/api/stock-prices', // Use your existing endpoint for prices
            method: 'POST',
            data: {
                'symbols[]': symbols, // Ensure your backend handles 'symbols[]'
                'csrf_token': $('meta[name="csrf-token"]').attr('content')
            },
            success: function(response) {
                if (response.success && response.prices) {
                    for (const symbol in response.prices) {
                        const priceData = response.prices[symbol];
                        const priceDisplay = $(`#watchlist-container .price-display[data-symbol="${symbol}"]`);
                        if (priceDisplay.length) {
                            let changeClass = priceData.change_percent >= 0 ? 'text-success' : 'text-danger';
                            let icon = priceData.change_percent >= 0 ? '<i class="fas fa-caret-up"></i>' : '<i class="fas fa-caret-down"></i>';
                            priceDisplay.html(`$${parseFloat(priceData.price).toFixed(2)} <span class="${changeClass}">(${parseFloat(priceData.change_percent).toFixed(2)}% ${icon})</span>`);
                        }
                    }
                }
            },
            error: function(xhr) {
                console.error("Error fetching watchlist prices:", xhr.responseText);
            }
        });
    }

    if ($('#watchlist-container li[data-watchlist-item]').length > 0) {
        fetchWatchlistPrices();
    }

    $(document).on('click', '.quick-analyze', function() {
        const symbol = $(this).data('symbol');
        $('#symbol').val(symbol); 
        $('#analyze-form').submit(); 
    });

    function showToast(message, type = 'info') {
        if (SELECTORS.toastContainer.length === 0) {
            $('body').append('<div id="toast-container" class="position-fixed bottom-0 end-0 p-3" style="z-index: 1056"></div>');
            SELECTORS.toastContainer = $('#toast-container');
        }
        
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
        
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            try {
                const toastElement = document.getElementById(toastId);
                const bsToast = new bootstrap.Toast(toastElement, { 
                    autohide: true, 
                    delay: CONFIG.toastDelay 
                });
                bsToast.show();
                
                toastElement.addEventListener('hidden.bs.toast', function() {
                    $(this).remove();
                });
                
                setTimeout(function() {
                    if ($('#' + toastId).length > 0) {
                        $('#' + toastId).remove();
                    }
                }, CONFIG.toastDelay + 1000);
            } catch (e) {
                console.error('Error showing toast:', e);
                toast.fadeIn().delay(CONFIG.toastDelay).fadeOut(function() {
                    $(this).remove();
                });
            }
        } else {
            console.warn('Bootstrap Toast not available, using fallback');
            toast.fadeIn().delay(CONFIG.toastDelay).fadeOut(function() {
                $(this).remove();
            });
        }
    }

    function updateCounts() {
        const analysesTable = $('#analyses-table');
        const buyCountElement = $('#buy-count');
        const sellCountElement = $('#sell-count');
        const analysisCountElement = $('#analysis-count');
        const watchlistCountElement = $('#watchlist-count');
        const watchlistContainer = $('#watchlist-container');
        
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
        
        if (buyCountElement.length) buyCountElement.text(buyCount);
        if (sellCountElement.length) sellCountElement.text(sellCount);
        if (analysisCountElement.length) analysisCountElement.text(analysesTable.find('tbody tr').length);
        if (watchlistCountElement.length && watchlistContainer.length) {
            watchlistCountElement.text(watchlistContainer.find('li:not(#empty-watchlist)').length);
        }
    }

    const loadStockPrices = debounce(function() {
        const symbolsToFetch = new Set();
         
        SELECTORS.priceDisplays = $('.price-display, .current-price');
        SELECTORS.tickerItems = $('.ticker-item');
        
        SELECTORS.priceDisplays.each(function() {
            const symbol = $(this).data('symbol');
            if(symbol) symbolsToFetch.add(symbol);
        });
        
        SELECTORS.tickerItems.each(function() {
            const symbol = $(this).data('symbol') || $(this).find('.ticker-symbol').text();
            if(symbol) symbolsToFetch.add(symbol);
        });

        if (symbolsToFetch.size === 0) return;

        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        $.ajax({
            url: CONFIG.api.stockPrices,
            method: 'POST',
            data: { symbols: Array.from(symbolsToFetch) },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    updatePriceDisplays(response.prices);
                } else {
                    showUnavailablePrices(symbolsToFetch);
                }
            },
            error: function(xhr) {
                showUnavailablePrices(symbolsToFetch);
            }
        });
    }, CONFIG.debounceDelay);
    
    function updatePriceDisplays(fetchedPrices) {
        SELECTORS.priceDisplays.each(function() {
            const element = $(this);
            const symbol = element.data('symbol');
            
            if (fetchedPrices[symbol]) {
                const currentPrice = parseFloat(fetchedPrices[symbol].price);
                if (!isNaN(currentPrice)) {
                    element.text('$' + currentPrice.toFixed(2)).removeClass('text-muted');
                    if (element.hasClass('current-price')) {
                        const row = element.closest('tr');
                        const plCell = row.find('.profit-loss');
                        plCell.text('--.--%').addClass('text-muted');
                    }
                } else {
                    element.text('$?.??').addClass('text-muted');
                }
            } else {
                element.text('$?.??').addClass('text-muted');
                if (element.hasClass('current-price')) {
                    const row = element.closest('tr');
                    const plCell = row.find('.profit-loss');
                    plCell.text('--.--%').addClass('text-muted');
                }
            }
        });
        
        SELECTORS.tickerItems.each(function() {
            const element = $(this);
            const symbol = element.find('.ticker-symbol').text();
            
            if (fetchedPrices[symbol]) {
                const priceData = fetchedPrices[symbol];
                const priceElement = element.find('.ticker-price');
                const changeElement = element.find('.ticker-change');
                
                priceElement.text('$' + parseFloat(priceData.price).toFixed(2));
                const changePercent = parseFloat(priceData.change_percent);
                const changeText = (changePercent >= 0 ? '+' : '') + changePercent.toFixed(2) + '%';
                changeElement.text(changeText);
                changeElement.removeClass('positive negative').addClass(changePercent >= 0 ? 'positive' : 'negative');
            } else {
                const priceElement = element.find('.ticker-price');
                const changeElement = element.find('.ticker-change');
                priceElement.text('$?.??');
                changeElement.text('--.--%');
                changeElement.removeClass('positive negative');
            }
        });
    }
    
    function showUnavailablePrices(symbolsToFetch) {
        SELECTORS.priceDisplays.each(function() {
            const element = $(this);
            element.text('N/A').addClass('text-muted');
            if (element.hasClass('current-price')) {
                const row = element.closest('tr');
                const plCell = row.find('.profit-loss');
                plCell.text('N/A').addClass('text-muted');
            }
        });
        
        SELECTORS.tickerItems.each(function() {
            const element = $(this);
            const priceElement = element.find('.ticker-price');
            const changeElement = element.find('.ticker-change');
            priceElement.text('N/A');
            changeElement.text('N/A');
            changeElement.removeClass('positive negative');
        });
    }

    $('#analyze-form').on('submit', function(e) {
        e.preventDefault();
        
        const symbolInput = $('#symbol');
        const symbol = symbolInput.val().toUpperCase().trim();
        const form = $(this);
        const button = form.find('button[type="submit"]');
        const originalButtonHtml = button.html();

        if (!symbol) {
            showToast('Please enter a stock symbol.', 'warning');
            symbolInput.focus();
            return;
        }
        
        const symbolPattern = /^[A-Z0-9.-]{1,10}$/;
        if (!symbolPattern.test(symbol)) {
            showToast('Invalid symbol format. Please enter a valid stock symbol.', 'warning');
            symbolInput.focus();
            return;
        }

        button.html('<span class="spinner-border spinner-border-sm me-2"></span>Analyzing...').prop('disabled', true);

        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        $.ajax({
            url: CONFIG.api.analyze,
            method: 'POST',
            data: { symbol: symbol },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success && response.analysis_id) {
                    showToast(`Analysis completed for ${response.symbol}!`, 'success');
                    symbolInput.val('');
                    button.html(originalButtonHtml).prop('disabled', false);
                    window.location.href = `/analysis/${response.analysis_id}`;
                } else {
                    showToast(response.error || 'Analysis failed.', 'danger');
                    button.html(originalButtonHtml).prop('disabled', false);
                }
            },
            error: function(xhr) {
                const errorMsg = xhr.responseJSON?.error || 'Error communicating with server.';
                showToast(errorMsg, 'danger');
                button.html(originalButtonHtml).prop('disabled', false);
            }
        });
    });
    
    function requestNewAnalysis(symbol, button, originalButtonHtml, symbolInput) {
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
                const errorMsg = xhr.responseJSON?.error || 'Server error starting new analysis.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                button.html(originalButtonHtml).prop('disabled', false);
            }
        });
    }

    $('body').on('click', '.add-watchlist', function() {
        const symbol = $(this).data('symbol');
        const button = $(this);
        const originalHtml = button.html();

        if (!symbol) {
            showToast('Invalid symbol', 'warning');
            return;
        }

        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);

        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

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
                const errorMsg = xhr.responseJSON?.error || 'Server error adding to watchlist.';
                showToast(errorMsg, 'danger');
                button.html(originalHtml);
            },
            complete: function() {
                button.prop('disabled', false);
            }
        });
    });

    $('body').on('click', '.remove-watchlist, .remove-watchlist-alt', function() {
        const symbol = $(this).data('symbol');
        const button = $(this);
        const originalHtml = button.html();
        
        if (!symbol) {
            showToast('Invalid symbol', 'warning');
            return;
        }

        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);

        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

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
                const errorMsg = xhr.responseJSON?.error || 'Server error removing from watchlist.';
                showToast(errorMsg, 'danger');
                button.html(originalHtml);
            },
            complete: function() {
                button.prop('disabled', false);
            }
        });
    });
    
    function updateWatchlistButtonsAdd(clickedButton, symbol) {
        const isAnalysisPageButton = clickedButton.closest('.stock-header').length > 0;
        
        if(isAnalysisPageButton) { 
            clickedButton.addClass('d-none');
            $('.remove-watchlist[data-symbol="' + symbol + '"]').removeClass('d-none');
        } else {
            clickedButton
                .removeClass('add-watchlist btn-outline-success btn-outline-warning')
                .addClass('remove-watchlist-alt btn-outline-danger')
                .html('<i class="fas fa-times"></i>')
                .attr('title', 'Remove from Watchlist');
                
            $(`.add-watchlist[data-symbol='${symbol}']`).not(clickedButton).addClass('d-none');
            $(`.remove-watchlist-alt[data-symbol='${symbol}']`).not(clickedButton).removeClass('d-none');
        }
        
        if (!isAnalysisPageButton) {
            $(`.add-watchlist[data-symbol='${symbol}']`).addClass('d-none');
            $(`.remove-watchlist[data-symbol='${symbol}']`).removeClass('d-none');
        }
    }
    
    function updateWatchlistButtonsRemove(clickedButton, symbol) {
        const isAnalysisPageButton = clickedButton.closest('.stock-header').length > 0;
        
        if(isAnalysisPageButton) {
            clickedButton.addClass('d-none');
            $('.add-watchlist[data-symbol="' + symbol + '"]').removeClass('d-none');
        } else {
            clickedButton
                .removeClass('remove-watchlist remove-watchlist-alt btn-warning btn-outline-danger')
                .addClass('add-watchlist btn-outline-success')
                .html('<i class="fas fa-star"></i>')
                .attr('title', 'Add to Watchlist');
                
            $(`.remove-watchlist-alt[data-symbol='${symbol}']`).not(clickedButton).addClass('d-none');
            $(`.add-watchlist[data-symbol='${symbol}']`).not(clickedButton).removeClass('d-none');
        }
        
        if (!isAnalysisPageButton) {
            $(`.remove-watchlist[data-symbol='${symbol}']`).addClass('d-none'); 
            $(`.add-watchlist[data-symbol='${symbol}']`).removeClass('d-none');
        }
    }
    
    function updateWatchlistContainer(symbol) {
        const watchlistContainer = $('#watchlist-container');
        
        if (watchlistContainer.length > 0) {
            if (watchlistContainer.find('li').filter(function() { 
                return $(this).find('.fw-bold').text() === symbol; 
            }).length === 0) {
                const newItem = $(`
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div><span class="fw-bold">${symbol}</span><span class="price-display ms-2 small text-muted" data-symbol="${symbol}">$--.--</span></div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary quick-analyze" data-symbol="${symbol}" title="Quick Analyze"><i class="fas fa-chart-line"></i></button>
                            <button class="btn btn-sm btn-outline-danger remove-watchlist" data-symbol="${symbol}" title="Remove from Watchlist"><i class="fas fa-times"></i></button>
                        </div>
                    </li>
                `);
                
                $('#empty-watchlist').hide();
                watchlistContainer.append(newItem);
                loadStockPrices();
            }
        }
    }
    
    function removeFromWatchlistContainer(symbol) {
        const watchlistContainer = $('#watchlist-container');
        const emptyWatchlist = $('#empty-watchlist');
        
        if (watchlistContainer.length > 0) {
            watchlistContainer.find('li').filter(function() { 
                return $(this).find('.fw-bold').text() === symbol; 
            }).fadeOut(300, function() {
                $(this).remove();
                if (watchlistContainer.find('li:not(#empty-watchlist)').length === 0 && emptyWatchlist.length > 0) {
                    emptyWatchlist.show();
                }
            });
        }
    }

    const initActionButtons = function() {
        if ($('.set-action').length > 0) {
            $('.set-action').on('click', handleActionButtonClick);
        }
    };
    
    function handleActionButtonClick() {
        const button = $(this);
        const action = button.data('action');
        const analysis_id = button.data('id');
        const originalHtml = button.html();
        const actionButtons = $('.set-action');

        if (!analysis_id) {
            showToast("Cannot set action: Analysis ID missing.", "danger");
            return;
        }

        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);
        actionButtons.not(button).prop('disabled', true);

        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        $.ajax({
            url: CONFIG.api.setAction,
            method: 'POST',
            data: { analysis_id: analysis_id, action: action },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    const actionText = action.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                    showToast(`Action set to ${actionText}.`, 'success');
                    updateActionButtonStatus(button, actionText);
                } else {
                    showToast(response.error || 'Failed to set action.', 'danger');
                }
            },
            error: function(xhr) {
                const errorMsg = xhr.responseJSON?.error || 'Server error setting action.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                button.html(originalHtml);
                actionButtons.prop('disabled', false);
            }
        });
    }
    
    function updateActionButtonStatus(activeButton, actionText) {
        $('.set-action').removeClass('active');
        activeButton.addClass('active');

        const statusBadge = $('#action-status .badge');
        if (statusBadge.length) {
            statusBadge
                .text(`Current Action: ${actionText}`)
                .removeClass('bg-secondary bg-info')
                .addClass('bg-info');
        }
    }

    $('body').on('click', '.share-analysis', function() {
        const id = $(this).data('id');
        const button = $(this);
        
        if (!id) {
            showToast("Missing analysis ID", "warning");
            return;
        }
        
        const originalIcon = button.find('i').attr('class');
        button.find('i').removeClass().addClass('fas fa-spinner fa-spin');

        $.ajax({
            url: CONFIG.api.share + id,
            method: 'GET',
            dataType: 'json',
            success: function(response) {
                if (response.share_url) {
                    const shareLinkInput = $('#share-link');
                    if (shareLinkInput.length) {
                        shareLinkInput.val(response.share_url);
                        const shareModalLabel = $('#shareModalLabel');
                        if (shareModalLabel.length) {
                            shareModalLabel.text(`Share Analysis (ID: ${id})`);
                        }
                    
                        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                            try {
                                const shareModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('shareModal'));
                                if (shareModal) {
                                    shareModal.show();
                                } else {
                                    throw new Error('Modal instance not created');
                                }
                            } catch (e) {
                                showToast('Share URL: ' + response.share_url, 'success');
                            }
                        } else {
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
                const errorMsg = xhr.responseJSON?.error || 'Error retrieving share link.';
                showToast(errorMsg, 'danger');
            },
            complete: function() {
                button.find('i').removeClass().addClass(originalIcon);
            }
        });
    });
    
    $('body').on('click', '.delete-analysis', function() {
        const id = $(this).data('id');
        const button = $(this);
        const row = button.closest('tr');
        
        if (!id) {
            showToast("Missing analysis ID", "warning");
            return;
        }
        
        if (!confirm('Are you sure you want to delete this analysis? This action cannot be undone.')) {
            return;
        }
        
        const originalIcon = button.find('i').attr('class');
        button.find('i').removeClass().addClass('fas fa-spinner fa-spin');
        button.prop('disabled', true);

        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
        
        $.ajax({
            url: CONFIG.api.deleteAnalysis,
            method: 'POST',
            data: { analysis_id: id },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    row.fadeOut(300, function() {
                        $(this).remove();
                        updateCounts();
                        if ($('#analyses-table tbody tr').length === 0) {
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
                const errorMsg = xhr.responseJSON?.error || 'Server error deleting analysis.';
                showToast(errorMsg, 'danger');
                button.find('i').removeClass().addClass(originalIcon);
                button.prop('disabled', false);
            }
        });
    });

    $('#copy-link').on('click', function() {
        const copyText = document.getElementById('share-link');
        const button = $(this);
        
        if (!copyText || !copyText.value) {
            showToast('No link to copy', 'warning');
            return;
        }
        
        try {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(copyText.value)
                    .then(() => {
                        const originalText = button.html();
                        button.html('<i class="fas fa-check me-1"></i> Copied!');
                        setTimeout(() => { button.html(originalText); }, 2500);
                    })
                    .catch(err => {
                        fallbackCopyTextToClipboard(copyText);
                    });
            } else {
                fallbackCopyTextToClipboard(copyText);
            }
        } catch (err) {
            showToast('Failed to copy link.', 'warning');
        }
    });
    
    function fallbackCopyTextToClipboard(copyText) {
        copyText.select();
        copyText.setSelectionRange(0, 99999); 
        try {
            const success = document.execCommand('copy');
            if (success) {
                showToast('Link copied to clipboard!', 'success');
            } else {
                showToast('Please press Ctrl+C to copy the link', 'info');
            }
        } catch (err) {
            showToast('Please press Ctrl+C to copy the link', 'info');
        }
    }

    $('body').on('click', '.quick-analyze', function() {
        const symbol = $(this).data('symbol');
        const button = $(this);
        const originalHtml = button.html();
        
        if (!symbol) {
            showToast('Missing symbol', 'warning');
            return;
        }
        
        if (!/^[A-Z0-9.-]{1,10}$/.test(symbol)) {
            showToast('Invalid symbol format', 'warning');
            return;
        }
        
        button.html('<span class="spinner-border spinner-border-sm"></span>').prop('disabled', true);
        
        const csrfToken = getCSRFToken();
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
        
        $.ajax({
            url: CONFIG.api.analyze,
            method: 'POST',
            data: { symbol: symbol },
            headers: headers,
            dataType: 'json',
            success: function(response) {
                if (response.success && response.analysis_id) {
                    window.location.href = `/analysis/${response.analysis_id}`;
                } else {
                    showToast('Analysis failed for this symbol', 'warning');
                    button.html(originalHtml).prop('disabled', false);
                }
            },
            error: function(xhr) {
                showToast('Error running analysis', 'danger');
                button.html(originalHtml).prop('disabled', false);
            }
        });
    });

    $('#refresh-data').on('click', function() {
        const button = $(this);
        
        button.html('<span class="spinner-border spinner-border-sm"></span> Refreshing...').prop('disabled', true);

        debounce(function() {
            loadStockPrices();
            updateCounts();
            
            setTimeout(function() {
                button.html('<i class="fas fa-sync-alt"></i> Refresh Data').prop('disabled', false);
                showToast('Display data refreshed!', 'success');
            }, 750);
        }, CONFIG.debounceDelay)();
    });
    
    function initPageFeatures() {
        initActionButtons();
        
        if ($('#analyses-table').length > 0) {
            updateCounts();
            loadStockPrices();
        }
        
        initTooltips();
    }
    
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
    
    initPageFeatures();

}); // End of $(document).ready()