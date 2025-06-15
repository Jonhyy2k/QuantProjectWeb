$(document).ready(function() {
    $('.page-guide-trigger').each(function() {
        var modalId = $(this).data('modal-id');
        // Ensure modalId is valid before proceeding
        if (!modalId) {
            console.warn('Page guide trigger found without a data-modal-id:', this);
            return; // Skip this trigger if no modalId is specified
        }

        var localStorageKey = 'quantPulseGuide_' + modalId + '_shown';
        var modalElement = document.getElementById(modalId);

        if (!modalElement) {
            console.warn('Modal element with ID ' + modalId + ' not found for a page guide trigger.');
            return; // Skip if the modal element itself doesn't exist
        }

        try {
            // Show on first visit for this specific page's guide
            if (localStorage.getItem(localStorageKey) !== 'true') {
                if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                    var guideModal = new bootstrap.Modal(modalElement);
                    guideModal.show();
                    localStorage.setItem(localStorageKey, 'true');
                } else {
                    console.warn('Bootstrap Modal library not available. Cannot show guide automatically for ' + modalId);
                }
            }
        } catch (e) {
            console.error('Error accessing localStorage for ' + localStorageKey + ':', e);
        }

        // Attach click event to the icon to show its modal
        $(this).on('click', function() {
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                var guideModal = new bootstrap.Modal(modalElement);
                guideModal.show();
            } else {
                console.warn('Bootstrap Modal library not available. Cannot show guide on click for ' + modalId);
            }
        });
    });
});
