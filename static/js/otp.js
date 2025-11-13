// OTP Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const otpInput = document.getElementById('otp');
    
    // Auto-focus on OTP input
    setTimeout(() => {
        otpInput.focus();
    }, 400);
    
    // Auto-submit when 6 digits are entered
    otpInput.addEventListener('input', function() {
        // Remove any non-numeric characters
        this.value = this.value.replace(/[^0-9]/g, '');
        
        if (this.value.length === 6) {
            this.form.submit();
        }
    });
    
    // Only allow numbers
    otpInput.addEventListener('keydown', function(e) {
        if ([46, 8, 9, 27, 13, 35, 36, 37, 39].includes(e.keyCode) || 
            (e.keyCode === 65 && e.ctrlKey === true) || 
            (e.keyCode === 67 && e.ctrlKey === true) ||
            (e.keyCode === 86 && e.ctrlKey === true) ||
            (e.keyCode === 88 && e.ctrlKey === true) ||
            (e.keyCode >= 35 && e.keyCode <= 39)) {
            return;
        }
        
        if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105)) {
            e.preventDefault();
        }
    });
    
    // Handle paste
    otpInput.addEventListener('paste', function(e) {
        e.preventDefault();
        const pastedData = e.clipboardData.getData('text');
        const numbersOnly = pastedData.replace(/[^0-9]/g, '');
        this.value = numbersOnly.slice(0, 6);
        
        if (this.value.length === 6) {
            this.form.submit();
        }
    });
});

// Auto-hide flash messages
setTimeout(() => {
    const flashMessages = document.querySelector('.auth-flash-messages');
    if (flashMessages) {
        flashMessages.style.display = 'none';
    }
}, 5000);