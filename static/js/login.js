// Login Page JavaScript
function togglePasswordVisibility(fieldId) {
    const passwordInput = document.getElementById(fieldId);
    const toggleIcon = passwordInput.parentNode.querySelector('.toggle-password i');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        passwordInput.type = 'password';
        toggleIcon.classList.replace('fa-eye-slash', 'fa-eye');
    }
}

// Form submission handler
function handleLoginSubmission() {
    const form = document.getElementById('loginForm');
    const loginBtn = document.getElementById('loginBtn');
    const loginText = document.getElementById('loginText');
    const loginSpinner = document.getElementById('loginSpinner');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Show loading state
            if (loginBtn && loginText && loginSpinner) {
                loginBtn.disabled = true;
                loginText.textContent = 'Signing In...';
                loginSpinner.style.display = 'inline-block';
            }
            
            // Form will submit normally, backend will handle OTP redirect
        });
    }
}

// Auto-hide flash messages
function autoHideFlashMessages() {
    setTimeout(() => {
        const flashMessages = document.querySelector('.auth-flash-messages');
        if (flashMessages) {
            flashMessages.style.opacity = '0';
            flashMessages.style.transform = 'translateX(-50%) translateY(-20px)';
            setTimeout(() => {
                flashMessages.style.display = 'none';
            }, 300);
        }
    }, 5000);
}

// Prevent zoom on input focus for mobile
function preventZoomOnFocus() {
    const inputs = document.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.style.fontSize = '16px';
        });
    });
}

// Initialize all functionality
document.addEventListener('DOMContentLoaded', function() {
    preventZoomOnFocus();
    handleLoginSubmission();
    autoHideFlashMessages();
    
    // Preserve email on form error
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('error')) {
        // Form will preserve values via Flask template
    }
});