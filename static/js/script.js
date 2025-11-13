document.addEventListener('DOMContentLoaded', function() {
    // App State
    let currentUser = null;
    let selectedEmergencyType = null;
    let emojiRating = 0;
    let userLocation = null;
    let emergencyPreference = null;
    
    // Emergency Type Selection (for Emergency_report.html)
    const emergencyTypes = document.querySelectorAll('.emergency-type');
    const continueBtn = document.getElementById('continueBtn');
    const emergencyTypeInput = document.getElementById('emergencyType');
    
    if (emergencyTypes.length > 0) {
        emergencyTypes.forEach(type => {
            type.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Remove active class from all types
                emergencyTypes.forEach(t => t.classList.remove('active'));
                
                // Add active class to selected type
                this.classList.add('active');
                
                // Enable continue button
                if (continueBtn) {
                    continueBtn.style.opacity = '1';
                    continueBtn.style.pointerEvents = 'auto';
                }
                
                // Set emergency type value
                selectedEmergencyType = this.getAttribute('data-type');
                const typeName = this.querySelector('span').textContent;
                if (emergencyTypeInput) {
                    emergencyTypeInput.value = typeName;
                }
            });
        });
    }
    
    // Continue to report form
    if (continueBtn) {
        continueBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (document.getElementById('report-form-page')) {
                document.getElementById('emergency-types-page').classList.remove('active');
                document.getElementById('report-form-page').classList.add('active');
            }
        });
    }
    
    // Make phone call function
    window.makeCall = function(number) {
        if (typeof app !== 'undefined') {
            // For DroidScript
            app.StartActivity("android.intent.action.CALL", "tel:" + number);
        } else {
            // Fallback for browser testing
            window.location.href = 'tel:' + number;
        }
    };
    
    // Get Location Function
    function getLocation() {
        const locationContainer = document.getElementById('locationContainer');
        if (locationContainer) {
            locationContainer.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Getting your location...';
            
            // For DroidScript compatibility
            if (typeof app !== 'undefined' && app.GetLocation) {
                app.GetLocation(function(location) {
                    userLocation = location;
                    locationContainer.innerHTML = `<i class="fas fa-map-marker-alt"></i> ${location.address}`;
                });
            } else {
                // Fallback for browser testing
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        userLocation = {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            address: "Location obtained successfully"
                        };
                        locationContainer.innerHTML = '<i class="fas fa-map-marker-alt"></i> Location obtained successfully';
                    }, function(error) {
                        locationContainer.innerHTML = '<i class="fas fa-map-marker-alt"></i> Unable to get location';
                    });
                } else {
                    locationContainer.innerHTML = '<i class="fas fa-map-marker-alt"></i> Geolocation not supported';
                }
            }
        }
    }
    
    // Auto-get location when on report form page
    if (document.getElementById('report-form-page') && 
        document.getElementById('report-form-page').classList.contains('active')) {
        getLocation();
    }
    
    // Capture Camera Function
    function captureCamera() {
        if (typeof app !== 'undefined' && app.TakePhoto) {
            app.TakePhoto(function(path) {
                // Display the captured photo
                document.getElementById('photoPreview').style.display = 'block';
                document.getElementById('previewImg').src = path;
            });
        } else {
            // Fallback for browser testing
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.capture = 'camera';
            input.onchange = function(e) {
                const file = e.target.files[0];
                const reader = new FileReader();
                reader.onload = function(event) {
                    document.getElementById('photoPreview').style.display = 'block';
                    document.getElementById('previewImg').src = event.target.result;
                };
                reader.readAsDataURL(file);
            };
            input.click();
        }
    }
    
    // Capture Photo Button
    const capturePhotoBtn = document.getElementById('capturePhotoBtn');
    if (capturePhotoBtn) {
        capturePhotoBtn.addEventListener('click', function() {
            if (typeof app !== 'undefined') {
                app.RequestPermission("CAMERA", function(granted) {
                    if (granted) {
                        localStorage.setItem('cameraPermission', 'granted');
                        captureCamera();
                    } else {
                        alert("Camera permission is required to take photos");
                    }
                });
            } else {
                captureCamera();
            }
        });
    }
    
    // Gallery Button
    const galleryBtn = document.getElementById('galleryBtn');
    if (galleryBtn) {
        galleryBtn.addEventListener('click', function() {
            if (typeof app !== 'undefined' && app.PickImage) {
                app.PickImage(function(path) {
                    // Display the selected image
                    document.getElementById('photoPreview').style.display = 'block';
                    document.getElementById('previewImg').src = path;
                });
            } else {
                // Fallback for browser testing
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = 'image/*';
                input.onchange = function(e) {
                    const file = e.target.files[0];
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        document.getElementById('photoPreview').style.display = 'block';
                        document.getElementById('previewImg').src = event.target.result;
                    };
                    reader.readAsDataURL(file);
                };
                input.click();
            }
        });
    }
    
    // Emoji Rating (for feedback.html)
    const emojis = document.querySelectorAll('.emoji');
    if (emojis.length > 0) {
        emojis.forEach(emoji => {
            emoji.addEventListener('click', function() {
                const rating = this.getAttribute('data-rating');
                emojiRating = rating;
                
                emojis.forEach(e => {
                    if (e.getAttribute('data-rating') <= rating) {
                        e.classList.add('active');
                    } else {
                        e.classList.remove('active');
                    }
                });
            });
        });
    }
    
    // Emergency Report Form
    const emergencyReportForm = document.getElementById('emergencyReportForm');
    if (emergencyReportForm) {
        emergencyReportForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!selectedEmergencyType) {
                alert('Please select an emergency type first.');
                if (document.getElementById('emergency-types-page')) {
                    document.getElementById('report-form-page').classList.remove('active');
                    document.getElementById('emergency-types-page').classList.add('active');
                }
                return;
            }
            
            const description = document.getElementById('emergencyDescription').value;
            
            // For DroidScript, use their SendText function to send the report
            if (typeof app !== 'undefined') {
                // Send to emergency services
                const message = `EMERGENCY REPORT: ${selectedEmergencyType}\n\n${description || 'No description provided'}\n\nLocation: ${userLocation ? userLocation.address : 'Unknown location'}`;
                app.SendText(["09171234567", "09187654321"], message);
            }
            
            alert('Emergency report submitted successfully! Help is on the way.');
            window.location.href = 'index.html';
        });
    }
    
    // Feedback Form
    const feedbackForm = document.getElementById('feedbackForm');
    if (feedbackForm) {
        feedbackForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (emojiRating === 0) {
                alert('Please provide a rating.');
                return;
            }
            
            alert('Thank you for your feedback! We appreciate your input.');
            window.location.href = 'index.html';
        });
    }
    
    // Initialize the app with permissions check
    if (!localStorage.getItem('permissionsGranted')) {
        setTimeout(() => {
            if (confirm('1TERA needs access to your location and camera to function properly. Grant permissions?')) {
                localStorage.setItem('permissionsGranted', 'true');
                alert('Permissions granted!');
                
                // For DroidScript, request actual permissions
                if (typeof app !== 'undefined') {
                    app.RequestPermission("LOCATION");
                    app.RequestPermission("CAMERA");
                }
            }
        }, 1000);
    }
    
    // DroidScript specific initialization
    if (typeof app !== 'undefined') {
        // Set up back button handling for DroidScript
        app.SetBackButton(function() {
            // Handle back navigation
            if (window.history.length > 1) {
                window.history.back();
                return true;
            }
            return false;
        });
    }
});