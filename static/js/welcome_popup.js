$(document).ready(function() {
    // Logic for showing the welcome pop-up on first visit
    if (localStorage.getItem('quantPulseWelcomeShown') !== 'true') {
        var welcomeModalElement = document.getElementById('welcomePopupModal');
        if (welcomeModalElement && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            var welcomeModal = new bootstrap.Modal(welcomeModalElement);
            welcomeModal.show();
            localStorage.setItem('quantPulseWelcomeShown', 'true');
        } else {
            console.warn('Welcome modal element or Bootstrap library not found. Cannot show welcome popup automatically.');
        }
    }
});
