// Forgot Password JavaScript
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

// Password Validation
function initializePasswordValidation() {
    const newPasswordInput = document.getElementById('new_password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const submitBtn = document.getElementById('submitBtn');
    const passwordValidation = document.getElementById('passwordValidation');
    
    if (!newPasswordInput) return;
    
    function validatePassword(password, confirmPassword = '') {
        return {
            length: password.length >= 8,
            uppercase: /[A-Z]/.test(password),
            lowercase: /[a-z]/.test(password),
            special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
            match: password === confirmPassword && password.length > 0
        };
    }
    
    function updateValidationUI(rules) {
        // Update rules
        document.getElementById('rule-length').className = rules.length ? 'valid' : 'invalid';
        document.getElementById('rule-uppercase').className = rules.uppercase ? 'valid' : 'invalid';
        document.getElementById('rule-lowercase').className = rules.lowercase ? 'valid' : 'invalid';
        document.getElementById('rule-special').className = rules.special ? 'valid' : 'invalid';
        document.getElementById('rule-match').className = rules.match ? 'valid' : 'invalid';
        
        // Update icons
        document.querySelectorAll('.validation-rules li').forEach(li => {
            const icon = li.querySelector('i');
            icon.className = li.classList.contains('valid') ? 'fas fa-check' : 'fas fa-times';
        });
        
        // Update strength bar
        const strengthBar = document.getElementById('strength-bar');
        const validRules = Object.values(rules).filter(Boolean).length - 1; // Exclude match rule
        
        if (validRules === 0) {
            strengthBar.className = 'strength-bar';
        } else if (validRules <= 2) {
            strengthBar.className = 'strength-bar strength-weak';
        } else if (validRules === 3) {
            strengthBar.className = 'strength-bar strength-medium';
        } else {
            strengthBar.className = 'strength-bar strength-strong';
        }
        
        // Update submit button
        const isPasswordValid = rules.length && rules.uppercase && rules.lowercase && rules.special && rules.match;
        if (submitBtn) {
            submitBtn.disabled = !isPasswordValid;
        }
    }
    
    // Show/hide validation based on user interaction
    let validationVisible = false;
    
    function showValidation() {
        if (!validationVisible) {
            passwordValidation.classList.add('show');
            validationVisible = true;
        }
    }
    
    function hideValidation() {
        if (validationVisible && !newPasswordInput.value && !confirmPasswordInput.value) {
            passwordValidation.classList.remove('show');
            validationVisible = false;
        }
    }
    
    // Event listeners for password validation
    newPasswordInput.addEventListener('focus', showValidation);
    newPasswordInput.addEventListener('input', function() {
        showValidation();
        const rules = validatePassword(this.value, confirmPasswordInput.value);
        updateValidationUI(rules);
    });
    
    newPasswordInput.addEventListener('blur', function() {
        setTimeout(hideValidation, 200);
    });
    
    confirmPasswordInput.addEventListener('focus', showValidation);
    confirmPasswordInput.addEventListener('input', function() {
        showValidation();
        const rules = validatePassword(newPasswordInput.value, this.value);
        updateValidationUI(rules);
    });
    
    confirmPasswordInput.addEventListener('blur', function() {
        setTimeout(hideValidation, 200);
    });
    
    // Initial validation state
    const initialRules = validatePassword(newPasswordInput.value, confirmPasswordInput.value);
    updateValidationUI(initialRules);
}

// OTP Input Handling
function initializeOTPInput() {
    const otpInput = document.getElementById('otp');
    if (!otpInput) return;
    
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
}

// Form submission handler
function handleFormSubmission() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('.submit-btn');
            const submitText = this.querySelector('#submitText');
            const submitSpinner = this.querySelector('#submitSpinner');
            
            if (submitBtn && submitText && submitSpinner) {
                submitBtn.disabled = true;
                submitText.textContent = 'Processing...';
                submitSpinner.style.display = 'inline-block';
            }
        });
    });
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
    handleFormSubmission();
    autoHideFlashMessages();
    initializePasswordValidation();
    initializeOTPInput();
});