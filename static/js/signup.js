// Signup Page JavaScript with Password Validation
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
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const signupBtn = document.getElementById('signupBtn');
    const passwordValidation = document.getElementById('passwordValidation');
    
    if (!passwordInput) return;
    
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
        if (signupBtn) {
            signupBtn.disabled = !isPasswordValid;
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
        // Only hide if both password fields are empty
        if (validationVisible && !passwordInput.value && !confirmPasswordInput.value) {
            passwordValidation.classList.remove('show');
            validationVisible = false;
        }
    }
    
    // Event listeners for password validation
    passwordInput.addEventListener('focus', showValidation);
    passwordInput.addEventListener('input', function() {
        showValidation();
        const rules = validatePassword(this.value, confirmPasswordInput.value);
        updateValidationUI(rules);
    });
    
    passwordInput.addEventListener('blur', function() {
        setTimeout(hideValidation, 200); // Small delay to allow clicking on other fields
    });
    
    confirmPasswordInput.addEventListener('focus', showValidation);
    confirmPasswordInput.addEventListener('input', function() {
        showValidation();
        const rules = validatePassword(passwordInput.value, this.value);
        updateValidationUI(rules);
    });
    
    confirmPasswordInput.addEventListener('blur', function() {
        setTimeout(hideValidation, 200);
    });
    
    // Initial validation state
    const initialRules = validatePassword(passwordInput.value, confirmPasswordInput.value);
    updateValidationUI(initialRules);
}

// Set max date for birthday
function setMaxBirthdayDate() {
    const birthdayInput = document.getElementById('birthday');
    if (birthdayInput) {
        const maxDate = new Date();
        maxDate.setFullYear(maxDate.getFullYear() - 13);
        birthdayInput.max = maxDate.toISOString().split('T')[0];
    }
}

// Auto-hide flash messages
function autoHideFlashMessages() {
    setTimeout(() => {
        const flashMessages = document.querySelector('.auth-flash-messages');
        if (flashMessages) {
            flashMessages.style.display = 'none';
        }
    }, 5000);
}

// Form submission handler
function handleFormSubmission() {
    const form = document.getElementById('signupForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            // Final validation before submission
            if (password !== confirmPassword) {
                e.preventDefault();
                flash('Passwords do not match!', 'error');
                return;
            }
            
            if (password.length < 8) {
                e.preventDefault();
                flash('Password must be at least 8 characters long!', 'error');
                return;
            }
            
            if (!/[A-Z]/.test(password)) {
                e.preventDefault();
                flash('Password must contain at least one uppercase letter!', 'error');
                return;
            }
            
            if (!/[a-z]/.test(password)) {
                e.preventDefault();
                flash('Password must contain at least one lowercase letter!', 'error');
                return;
            }
            
            if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
                e.preventDefault();
                flash('Password must contain at least one special character!', 'error');
                return;
            }
        });
    }
}

// Prevent zoom on input focus for mobile
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.style.fontSize = '16px';
        });
    });
    
    setMaxBirthdayDate();
    initializePasswordValidation();
    handleFormSubmission();
    autoHideFlashMessages();
});