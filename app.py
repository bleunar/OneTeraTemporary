from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import mysql.connector
from flask_mail import Mail, Message
import bcrypt
import os
from datetime import datetime, timedelta
import json
import random
import secrets
from werkzeug.utils import secure_filename
from admin import admin_bp
import pytz
import hashlib

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Timezone configuration
MANILA_TZ = pytz.timezone('Asia/Manila')

app = Flask(__name__)

# Register admin blueprint
app.register_blueprint(admin_bp)
# Basic configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# MySQL Configuration 
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')  
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', '1tera_system')

# File upload configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'default@example.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['ADMIN_EMAIL'] = os.environ.get('MAIL_USERNAME', 'default@example.com')
app.config['MAIL_SUPPRESS_SEND'] = False  

# Initialize mail
mail = Mail(app)

# Deployment configuration
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 5000))
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production').lower()
DEBUG = ENVIRONMENT == 'development'

def get_hotline_icon(category):
    icons = {
        'police': 'shield-alt',
        'fire': 'fire',
        'medical': 'truck-medical',
        'rescue': 'life-ring',
        'coast_guard': 'water',
        'disaster': 'house-damage'
    }
    return icons.get(category, 'phone')

# Register the template filter
app.jinja_env.filters['get_hotline_icon'] = get_hotline_icon

def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp):
    """Send OTP to user's email"""
    try:
        msg = Message(
            subject='1TERA - OTP Verification',
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f'''
        Your OTP for 1TERA verification is: {otp}
        
        This OTP will expire in 10 minutes.
        
        If you didn't request this, please ignore this email.
        
        Stay safe,
        1TERA Team
        '''
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False

def get_device_fingerprint():
    """Generate a persistent device fingerprint based on user agent and IP"""
    user_agent = request.headers.get('User-Agent', '')[:200]  # Limit length
    ip = request.remote_addr
    
    # Create hash of user agent + IP for consistent fingerprinting
    fingerprint_data = f"{user_agent}|{ip}".encode()
    return hashlib.sha256(fingerprint_data).hexdigest()[:32]  

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file and return filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # timestamp 
        timestamp = datetime.now(MANILA_TZ).strftime("%Y%m%d_%H%M%S_")
        filename = timestamp + filename
        
        # upload 
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None

# Routes
@app.route('/admin-access')
def admin_access():
    """Redirect to admin login"""
    return redirect(url_for('admin.admin_login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if OTP verification is required for this device
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('index.html', recent_reports=[], alerts=[])
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get user's recent reports
        cur.execute("""
            SELECT er.*, u.fname, u.lname 
            FROM emergency_reports er 
            LEFT JOIN users u ON er.user_id = u.id 
            WHERE er.user_id = %s
            ORDER BY er.created_at DESC 
            LIMIT 5
        """, (session['user_id'],))
        recent_reports = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Get recent alerts (only from last 24 hours)
        alerts = get_recent_alerts()
        
        return render_template('index.html', recent_reports=recent_reports, alerts=alerts)
        
    except Exception as e:
        print(f"Error fetching data for index: {e}")
        conn.close()
        return render_template('index.html', recent_reports=[], alerts=[])

def get_recent_alerts(limit=5):
    """Get recent alerts from admin_alerts table that are within 24 hours"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(dictionary=True)
        # Get alerts from the last 24 hours only
        cur.execute("""
            SELECT * FROM admin_alerts 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
        alerts = cur.fetchall()
        cur.close()
        conn.close()
        return alerts
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        conn.close()
        return []

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('login.html')
        
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
                # Check if this device is trusted
                device_fingerprint = get_device_fingerprint()
                cur.execute("""
                    SELECT * FROM trusted_devices 
                    WHERE user_id = %s AND device_fingerprint = %s
                """, (user['id'], device_fingerprint))
                trusted_device = cur.fetchone()
                
                if trusted_device:
                    # Device is trusted, log in directly
                    session['user_id'] = user['id']
                    session['user_email'] = user['email']
                    session['user_name'] = f"{user['fname']} {user['lname']}"
                    session['otp_verified'] = True
                    flash('Login successful!', 'success')
                    return redirect(url_for('index'))
                else:
                    # New device, require OTP verification
                    otp = generate_otp()
                    otp_expiry = datetime.now(MANILA_TZ) + timedelta(minutes=10)
                    
                    # Store OTP in database
                    cur.execute("""
                        INSERT INTO otp_verifications (user_id, otp, expiry, device_fingerprint)
                        VALUES (%s, %s, %s, %s)
                    """, (user['id'], otp, otp_expiry, device_fingerprint))
                    
                    # Send OTP email
                    if send_otp_email(email, otp):
                        session['pending_user_id'] = user['id']
                        session['pending_email'] = email
                        session['pending_name'] = f"{user['fname']} {user['lname']}"
                        conn.commit()
                        cur.close()
                        conn.close()
                        return redirect(url_for('verify_otp'))
                    else:
                        flash('Error sending OTP. Please try again.', 'error')
            else:
                flash('Invalid email or password', 'error')
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login error. Please try again.', 'error')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            fname = request.form['fname']
            lname = request.form['lname']
            phone_num = request.form['phone_num']
            age = int(request.form['age'])
            birthday = request.form['birthday']
            email = request.form['email']
            password = request.form['password']
            confirmPassword = request.form['confirmPassword']
            
            # Validate passwords match
            if password != confirmPassword:
                flash('Passwords do not match!', 'error')
                return render_template('signup.html')
            
            # Enhanced password strength validation
            if len(password) < 8:
                flash('Password must be at least 8 characters long!', 'error')
                return render_template('signup.html')
            
            if not any(char.isupper() for char in password):
                flash('Password must contain at least one uppercase letter!', 'error')
                return render_template('signup.html')
            
            if not any(char.islower() for char in password):
                flash('Password must contain at least one lowercase letter!', 'error')
                return render_template('signup.html')
            
            if not any(char in '!@#$%^&*()_+-=[]{};:\'",.<>?/\\|' for char in password):
                flash('Password must contain at least one special character!', 'error')
                return render_template('signup.html')
            
            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('signup.html')
            
            cur = conn.cursor()
            
            # Check if email already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Email already registered!', 'error')
                cur.close()
                conn.close()
                return render_template('signup.html')
            
            # Generate OTP for new user verification
            otp = generate_otp()
            otp_expiry = datetime.now(MANILA_TZ) + timedelta(minutes=10)
            
            # Store user data in session for OTP verification
            session['pending_signup'] = {
                'fname': fname,
                'lname': lname,
                'phone_num': phone_num,
                'age': age,
                'birthday': birthday,
                'email': email,
                'password': hashed_password.decode('utf-8'),
                'otp': otp,
                'otp_expiry': otp_expiry.isoformat()
            }
            
            # Send OTP email
            if send_otp_email(email, otp):
                conn.close()
                return redirect(url_for('verify_signup_otp'))
            else:
                flash('Error sending OTP. Please try again.', 'error')
                session.pop('pending_signup', None)
            
        except Exception as e:
            print(f"Signup error: {e}")
            flash('Error creating account. Please try again.', 'error')
    
    return render_template('signup.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'pending_user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        otp = request.form['otp']
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('otp.html', purpose='login')
        
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT * FROM otp_verifications 
                WHERE user_id = %s AND otp = %s AND expiry > %s
            """, (session['pending_user_id'], otp, datetime.now(MANILA_TZ)))
            
            otp_record = cur.fetchone()
            
            if otp_record:
                # OTP is valid
                device_fingerprint = get_device_fingerprint()
                
                # Add device to trusted devices
                cur.execute("""
                    INSERT INTO trusted_devices (user_id, device_fingerprint)
                    VALUES (%s, %s)
                """, (session['pending_user_id'], device_fingerprint))
                
                # Delete used OTP
                cur.execute("DELETE FROM otp_verifications WHERE id = %s", (otp_record['id'],))
                
                # Set session variables
                session['user_id'] = session['pending_user_id']
                session['user_email'] = session['pending_email']
                session['user_name'] = session['pending_name']
                session['otp_verified'] = True
                
                # Clean up session
                session.pop('pending_user_id', None)
                session.pop('pending_email', None)
                session.pop('pending_name', None)
                
                conn.commit()
                cur.close()
                conn.close()
                
                flash('OTP verified successfully!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid or expired OTP. Please try again.', 'error')
                
        except Exception as e:
            print(f"OTP verification error: {e}")
            flash('Error verifying OTP. Please try again.', 'error')
        finally:
            conn.close()
    
    return render_template('otp.html', purpose='login')

@app.route('/verify-signup-otp', methods=['GET', 'POST'])
def verify_signup_otp():
    if 'pending_signup' not in session:
        return redirect(url_for('signup'))
    
    if request.method == 'POST':
        otp = request.form['otp']
        pending_data = session['pending_signup']
        
        # Check if OTP matches and is not expired
        if (otp == pending_data['otp'] and 
            datetime.fromisoformat(pending_data['otp_expiry']) > datetime.now(MANILA_TZ)):
            
            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('otp.html', purpose='signup')
            
            try:
                cur = conn.cursor()
                
                # Insert new user
                cur.execute("""
                    INSERT INTO users (fname, lname, phone_num, age, birthday, email, password)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    pending_data['fname'], 
                    pending_data['lname'], 
                    pending_data['phone_num'], 
                    pending_data['age'], 
                    pending_data['birthday'], 
                    pending_data['email'], 
                    pending_data['password']
                ))
                
                # Get the new user ID
                user_id = cur.lastrowid
                
                # Add current device to trusted devices
                device_fingerprint = get_device_fingerprint()
                cur.execute("""
                    INSERT INTO trusted_devices (user_id, device_fingerprint)
                    VALUES (%s, %s)
                """, (user_id, device_fingerprint))
                
                conn.commit()
                cur.close()
                conn.close()
                
                # Set session variables
                session['user_id'] = user_id
                session['user_email'] = pending_data['email']
                session['user_name'] = f"{pending_data['fname']} {pending_data['lname']}"
                session['otp_verified'] = True
                
                # Clean up session
                session.pop('pending_signup', None)
                
                flash('Account created successfully!', 'success')
                return redirect(url_for('index'))
                
            except Exception as e:
                print(f"Error creating user: {e}")
                flash('Error creating account. Please try again.', 'error')
                conn.close()
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')
    
    return render_template('otp.html', purpose='signup')

@app.route('/resend-otp')
def resend_otp():
    if 'pending_user_id' in session:
        # Resend OTP for login
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT email FROM users WHERE id = %s", (session['pending_user_id'],))
                user = cur.fetchone()
                
                if user:
                    otp = generate_otp()
                    otp_expiry = datetime.now(MANILA_TZ) + timedelta(minutes=10)
                    
                    # Update OTP in database
                    cur.execute("""
                        UPDATE otp_verifications 
                        SET otp = %s, expiry = %s 
                        WHERE user_id = %s
                    """, (otp, otp_expiry, session['pending_user_id']))
                    
                    if send_otp_email(user['email'], otp):
                        conn.commit()
                        flash('New OTP sent to your email!', 'success')
                    else:
                        flash('Error sending OTP. Please try again.', 'error')
            except Exception as e:
                print(f"Resend OTP error: {e}")
                flash('Error resending OTP. Please try again.', 'error')
            finally:
                conn.close()
                
    elif 'pending_signup' in session:
        # Resend OTP for signup
        pending_data = session['pending_signup']
        otp = generate_otp()
        otp_expiry = datetime.now(MANILA_TZ) + timedelta(minutes=10)
        
        # Update OTP in session
        session['pending_signup']['otp'] = otp
        session['pending_signup']['otp_expiry'] = otp_expiry.isoformat()
        
        if send_otp_email(pending_data['email'], otp):
            flash('New OTP sent to your email!', 'success')
        else:
            flash('Error sending OTP. Please try again.', 'error')
    
    return redirect(request.referrer or url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/emergency_report', methods=['GET', 'POST'])
def emergency_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    if request.method == 'POST':
        emergency_type = request.form.get('emergency_type', '')
        description = request.form.get('description', '')
        location = request.form.get('location', 'Unknown Location')
        latitude = request.form.get('latitude', 0)
        longitude = request.form.get('longitude', 0)
        accept_terms = request.form.get('accept_terms', False)
        
        if not emergency_type:
            flash('Please select an emergency type', 'error')
            return render_template('emergency_report.html')
        
        # Validate terms and conditions
        if not accept_terms:
            flash('You must accept the Terms and Conditions to submit an emergency report', 'error')
            return render_template('emergency_report.html')
        
        # Handle file upload
        image_filename = None
        if 'emergency_image' in request.files:
            file = request.files['emergency_image']
            if file and file.filename != '':
                image_filename = save_uploaded_file(file)
                if not image_filename:
                    flash('Invalid file type. Please upload PNG, JPG, or GIF images only.', 'error')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('emergency_report.html')
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO emergency_reports (user_id, emergency_type, description, location, latitude, longitude, status, e_img)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
            """, (session['user_id'], emergency_type, description, location, latitude, longitude, image_filename))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash('Emergency report submitted successfully! Help is on the way.', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            print(f"Emergency report error: {e}")
            conn.close()
            flash('Error submitting emergency report. Please try again.', 'error')
    
    return render_template('emergency_report.html')

@app.route('/heatmaps')
def heatmaps():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('heatmaps.html', heatmap_data=[])
    
    try:
        cur = conn.cursor(dictionary=True)
        # Show ALL reports from ALL users within Tigbauan area
        cur.execute("""
            SELECT 
                er.*, 
                u.fname, 
                u.lname,
                CASE 
                    WHEN er.user_id = %s THEN 'my_report'
                    ELSE 'other_report'
                END as report_ownership
            FROM emergency_reports er 
            LEFT JOIN users u ON er.user_id = u.id 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
            AND latitude BETWEEN 10.60 AND 10.80  -- Tigbauan area latitude range
            AND longitude BETWEEN 122.30 AND 122.50  -- Tigbauan area longitude range
            ORDER BY er.created_at DESC
        """, (session['user_id'],))
        reports = cur.fetchall()
        cur.close()
        conn.close()
        
        heatmap_data = []
        for report in reports:
            heatmap_data.append({
                'id': report['id'],
                'type': report.get('emergency_type', 'unknown'),
                'lat': float(report.get('latitude', 0)),
                'lng': float(report.get('longitude', 0)),
                'description': report.get('description', ''),
                'status': report.get('status', 'pending'),
                'location': report.get('location', 'Unknown location'),
                'user_name': f"{report.get('fname', '')} {report.get('lname', '')}".strip(),
                'image': report.get('e_img', None),
                'ownership': report.get('report_ownership', 'other_report'),
                'time': report.get('created_at', datetime.now(MANILA_TZ)).strftime('%Y-%m-%d %H:%M') if isinstance(report.get('created_at'), datetime) else 'Unknown'
            })
        
        return render_template('heatmaps.html', heatmap_data=json.dumps(heatmap_data))
    
    except Exception as e:
        print(f"Heatmaps error: {e}")
        conn.close()
        return render_template('heatmaps.html', heatmap_data=[])
    
@app.route('/hotlines')
def hotlines():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('hotlines.html', hotlines=[])
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM hotlines ORDER BY category")
        hotlines_data = cur.fetchall()
        cur.close()
        conn.close()
        
        return render_template('hotlines.html', hotlines=hotlines_data)
    
    except Exception as e:
        print(f"Hotlines error: {e}")
        conn.close()
        return render_template('hotlines.html', hotlines=[])

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    if request.method == 'POST':
        rating = request.form.get('rating', 0)
        feedback_type = request.form.get('feedback_type', '')
        message = request.form.get('message', '')
        
        if not rating or not feedback_type or not message:
            flash('Please fill all required fields', 'error')
            return render_template('feedback.html')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('feedback.html')
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO feedback (user_id, rating, feedback_type, message)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], rating, feedback_type, message))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash('Thank you for your feedback!', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            print(f"Feedback error: {e}")
            conn.close()
            flash('Error submitting feedback. Please try again.', 'error')
    
    return render_template('feedback.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('index'))
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get user info
        cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cur.fetchone()
        
        if not user:
            flash('User not found', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('logout'))
        
        # Get report stats - ONLY FOR CURRENT USER
        cur.execute("SELECT COUNT(*) as count FROM emergency_reports WHERE user_id = %s", (session['user_id'],))
        total_reports = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM emergency_reports WHERE user_id = %s AND status = 'resolved'", (session['user_id'],))
        resolved_reports = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM emergency_reports WHERE user_id = %s AND status = 'pending'", (session['user_id'],))
        pending_reports = cur.fetchone()['count']
        
        cur.close()
        conn.close()
        
        return render_template('profile.html', 
                             user=user,
                             total_reports=total_reports,
                             resolved_reports=resolved_reports,
                             pending_reports=pending_reports)
    
    except Exception as e:
        print(f"Profile error: {e}")
        conn.close()
        flash('Error loading profile.', 'error')
        return redirect(url_for('index'))

@app.route('/view_status')
def view_status():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('index'))
    
    try:
        cur = conn.cursor(dictionary=True)
        # Only show reports from the current user with all fields including estimated_arrival
        cur.execute("""
            SELECT er.*, 
                   COALESCE(er.estimated_arrival, 'Not available') as estimated_arrival,
                   COALESCE(er.response_type, 'Not dispatched') as response_type
            FROM emergency_reports er 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (session['user_id'],))
        reports = cur.fetchall()
        cur.close()
        conn.close()
        
        return render_template('view_status.html', reports=reports)
    
    except Exception as e:
        print(f"View status error: {e}")
        conn.close()
        flash('Error loading report history.', 'error')
        return redirect(url_for('index'))
    

# notitfications
@app.route('/get_user_notifications')
def get_user_notifications():
    """Get notifications for the current user including admin alerts"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get unread notifications (both report updates and admin alerts)
        cur.execute("""
            (SELECT 
                un.id,
                un.user_id,
                un.report_id,
                un.notification_type,
                un.title,
                un.message,
                un.is_read,
                un.read_at,
                un.created_at,
                er.emergency_type,
                er.status as report_status,
                'user_notification' as source
            FROM user_notifications un
            LEFT JOIN emergency_reports er ON un.report_id = er.id
            WHERE un.user_id = %s)
            
            UNION ALL
            
            (SELECT 
                aa.id + 1000000 as id,  -- Add offset to avoid ID conflicts
                %s as user_id,
                NULL as report_id,
                aa.alert_type as notification_type,
                CASE 
                    WHEN aa.alert_type = 'danger' THEN '🚨 EMERGENCY ALERT'
                    WHEN aa.alert_type = 'warning' THEN '⚠️ IMPORTANT NOTICE' 
                    ELSE 'ℹ️ ADMIN ALERT'
                END as title,
                aa.message,
                IF(ua.id IS NULL, FALSE, TRUE) as is_read,
                ua.read_at,
                aa.created_at,
                NULL as emergency_type,
                NULL as report_status,
                'admin_alert' as source
            FROM admin_alerts aa
            LEFT JOIN user_alert_views ua ON aa.id = ua.alert_id AND ua.user_id = %s
            WHERE aa.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY aa.created_at DESC)
            
            ORDER BY created_at DESC
            LIMIT 50
        """, (session['user_id'], session['user_id'], session['user_id']))
        
        notifications = cur.fetchall()
        
        # Format notifications
        formatted_notifications = []
        for notification in notifications:
            # Determine icon based on notification type
            icon = get_notification_icon(notification['notification_type'])
            
            formatted_notifications.append({
                'id': notification['id'],
                'title': notification['title'],
                'message': notification['message'],
                'type': notification['notification_type'],
                'icon': icon,
                'report_id': notification['report_id'],
                'emergency_type': notification['emergency_type'],
                'created_at': notification['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': notification['is_read'],
                'source': notification['source']
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'notifications': formatted_notifications
        })
        
    except Exception as e:
        print(f"Get user notifications error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching notifications'})

# helper function notification icons
def get_notification_icon(notification_type):
    icons = {
        'pending': 'clock',
        'in_progress': 'spinner',
        'resolved': 'check-circle',
        'dispatched': 'paper-plane',
        'alert_info': 'info-circle',
        'alert_warning': 'exclamation-triangle',
        'alert_danger': 'exclamation-circle',
        'info': 'info-circle',
        'warning': 'exclamation-triangle',
        'danger': 'exclamation-circle'
    }
    return icons.get(notification_type, 'bell')


@app.route('/mark_notification_read/<int:notification_id>')
def mark_notification_read(notification_id):
    """Mark a notification as read (handles both user notifications and admin alerts)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        
        # Check if it's an admin alert (ID > 1000000)
        if notification_id > 1000000:
            alert_id = notification_id - 1000000
            # Mark admin alert as read by inserting into user_alert_views
            cur.execute("""
                INSERT IGNORE INTO user_alert_views (user_id, alert_id, read_at)
                VALUES (%s, %s, %s)
            """, (session['user_id'], alert_id, datetime.now(MANILA_TZ)))
        else:
            # Mark user notification as read
            cur.execute("""
                UPDATE user_notifications 
                SET is_read = TRUE, read_at = %s 
                WHERE id = %s AND user_id = %s
            """, (datetime.now(MANILA_TZ), notification_id, session['user_id']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
        
    except Exception as e:
        print(f"Mark notification read error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating notification'})

# mark notif
@app.route('/mark_all_notifications_read', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read for the current user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        
        # Mark all user notifications as read
        cur.execute("""
            UPDATE user_notifications 
            SET is_read = TRUE, read_at = %s 
            WHERE user_id = %s AND is_read = FALSE
        """, (datetime.now(MANILA_TZ), session['user_id']))
        
        # Mark all admin alerts as read
        cur.execute("""
            INSERT IGNORE INTO user_alert_views (user_id, alert_id, read_at)
            SELECT %s, aa.id, %s
            FROM admin_alerts aa
            WHERE aa.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            AND aa.id NOT IN (
                SELECT alert_id FROM user_alert_views WHERE user_id = %s
            )
        """, (session['user_id'], datetime.now(MANILA_TZ), session['user_id']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
        
    except Exception as e:
        print(f"Mark all notifications read error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating notifications'})

# unread
@app.route('/get_unread_notification_count')
def get_unread_notification_count():
    """Get count of unread notifications for the current user (including admin alerts)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'count': 0})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'count': 0})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Count unread user notifications
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM user_notifications 
            WHERE user_id = %s AND is_read = FALSE
        """, (session['user_id'],))
        user_notifications_count = cur.fetchone()['count']
        
        # Count unread admin alerts (from last 24 hours)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM admin_alerts aa
            WHERE aa.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            AND aa.id NOT IN (
                SELECT alert_id FROM user_alert_views WHERE user_id = %s
            )
        """, (session['user_id'],))
        admin_alerts_count = cur.fetchone()['count']
        
        total_count = user_notifications_count + admin_alerts_count
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': total_count,
            'user_notifications': user_notifications_count,
            'admin_alerts': admin_alerts_count
        })
        
    except Exception as e:
        print(f"Get unread notification count error: {e}")
        conn.close()
        return jsonify({'success': False, 'count': 0})
    
@app.route('/report_details/<int:report_id>')
def report_details(report_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('otp_verified') != True:
        return redirect(url_for('verify_otp'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('view_status'))
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get detailed report information including admin response data
        cur.execute("""
            SELECT 
                er.*,
                u.fname,
                u.lname,
                u.phone_num,
                u.email,
                COALESCE(er.estimated_arrival, 'Not available') as estimated_arrival,
                COALESCE(er.response_type, 'Not dispatched') as response_type,
                COALESCE(er.dispatcher_notes, 'No dispatcher notes') as dispatcher_notes,
                COALESCE(er.admin_notes, 'No admin notes') as admin_notes,
                COALESCE(er.response_notes, 'No response notes') as response_notes,
                au.full_name as responder_name,
                er.response_time,
                er.dispatched_at,
                er.updated_at
            FROM emergency_reports er 
            LEFT JOIN users u ON er.user_id = u.id 
            LEFT JOIN admin_users au ON er.responded_by = au.id
            WHERE er.id = %s AND er.user_id = %s
        """, (report_id, session['user_id']))
        
        report = cur.fetchone()
        
        if not report:
            flash('Report not found or access denied', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('view_status'))
        
        # Calculate time differences
        report_data = dict(report)
        
        # Format timestamps
        if report['created_at']:
            report_data['created_at_formatted'] = report['created_at'].strftime('%B %d, %Y at %I:%M %p')
        else:
            report_data['created_at_formatted'] = 'Unknown'
            
        if report['response_time']:
            report_data['response_time_formatted'] = report['response_time'].strftime('%B %d, %Y at %I:%M %p')
            # Calculate response time in minutes
            response_delay = (report['response_time'] - report['created_at']).total_seconds() / 60
            report_data['response_delay_minutes'] = round(response_delay, 1)
        else:
            report_data['response_time_formatted'] = 'Not responded yet'
            report_data['response_delay_minutes'] = None
            
        if report['updated_at']:
            report_data['updated_at_formatted'] = report['updated_at'].strftime('%B %d, %Y at %I:%M %p')
        else:
            report_data['updated_at_formatted'] = 'Never updated'
        
        cur.close()
        conn.close()
        
        return render_template('report_details.html', report=report_data)
    
    except Exception as e:
        print(f"Report details error: {e}")
        conn.close()
        flash('Error loading report details.', 'error')
        return redirect(url_for('view_status'))
    
@app.route('/delete_notification/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    """Permanently delete a notification from the database"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        
        # Check if it's a regular notification or admin alert
        if notification_id > 1000000:
            # It's an admin alert - mark it as read in user_alert_views
            alert_id = notification_id - 1000000
            cur.execute("""
                INSERT IGNORE INTO user_alert_views (user_id, alert_id, read_at)
                VALUES (%s, %s, %s)
            """, (session['user_id'], alert_id, datetime.now(MANILA_TZ)))
        else:
            # It's a regular user notification - delete it permanently
            cur.execute("""
                DELETE FROM user_notifications 
                WHERE id = %s AND user_id = %s
            """, (notification_id, session['user_id']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notification deleted successfully'})
        
    except Exception as e:
        print(f"Delete notification error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error deleting notification'})

# Forgot Password Routes
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('forgot_password.html', step='email')
        
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, fname, lname FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user:
                # Generate OTP for password reset
                otp = generate_otp()
                otp_expiry = datetime.now(MANILA_TZ) + timedelta(minutes=10)
                
                # Store OTP in session for verification (no database changes needed)
                session['reset_email'] = email
                session['reset_otp'] = otp
                session['reset_otp_expiry'] = otp_expiry.isoformat()
                session['reset_user_id'] = user['id']
                
                # Send OTP email
                if send_password_reset_email(email, otp, f"{user['fname']} {user['lname']}"):
                    flash('OTP sent to your email!', 'success')
                    cur.close()
                    conn.close()
                    return render_template('forgot_password.html', step='verify_otp', email=email)
                else:
                    flash('Error sending OTP. Please try again.', 'error')
            else:
                flash('No account found with this email address.', 'error')
                
        except Exception as e:
            print(f"Forgot password error: {e}")
            flash('Error processing request. Please try again.', 'error')
        finally:
            conn.close()
    
    return render_template('forgot_password.html', step='email')

@app.route('/verify-forgot-password-otp', methods=['POST'])
def verify_forgot_password_otp():
    email = request.form['email']
    otp = request.form['otp']
    
    # Verify OTP from session
    if (session.get('reset_email') == email and 
        session.get('reset_otp') == otp and
        datetime.fromisoformat(session.get('reset_otp_expiry')) > datetime.now(MANILA_TZ)):
        
        # OTP is valid, proceed to password reset
        session['reset_verified'] = True
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    else:
        flash('Invalid or expired OTP. Please try again.', 'error')
    
    return render_template('forgot_password.html', step='verify_otp', email=email)

@app.route('/reset-password', methods=['POST'])
def reset_password():
    email = request.form['email']
    otp = request.form['otp']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    # Verify session is still valid
    if not (session.get('reset_verified') and session.get('reset_email') == email):
        flash('Session expired. Please start the password reset process again.', 'error')
        return redirect(url_for('forgot_password'))
    
    # Validate passwords match
    if new_password != confirm_password:
        flash('Passwords do not match!', 'error')
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    
    # Enhanced password strength validation
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long!', 'error')
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    
    if not any(char.isupper() for char in new_password):
        flash('Password must contain at least one uppercase letter!', 'error')
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    
    if not any(char.islower() for char in new_password):
        flash('Password must contain at least one lowercase letter!', 'error')
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    
    if not any(char in '!@#$%^&*()_+-=[]{};:\'",.<>?/\\|' for char in new_password):
        flash('Password must contain at least one special character!', 'error')
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)
    
    try:
        cur = conn.cursor()
        
        # Hash the new password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update user's password in the existing users table
        cur.execute("UPDATE users SET password = %s WHERE email = %s", 
                   (hashed_password.decode('utf-8'), email))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Clear session variables
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_otp_expiry', None)
        session.pop('reset_user_id', None)
        session.pop('reset_verified', None)
        
        flash('Password reset successfully! You can now login with your new password.', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        print(f"Reset password error: {e}")
        flash('Error resetting password. Please try again.', 'error')
        conn.close()
    
    return render_template('forgot_password.html', step='reset_password', email=email, otp=otp)

@app.route('/resend-forgot-password-otp')
def resend_forgot_password_otp():
    email = request.args.get('email')
    
    if not email or session.get('reset_email') != email:
        flash('Invalid request. Please start the password reset process again.', 'error')
        return redirect(url_for('forgot_password'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('forgot_password'))
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, fname, lname FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if user:
            # Generate new OTP
            otp = generate_otp()
            otp_expiry = datetime.now(MANILA_TZ) + timedelta(minutes=10)
            
            # Update session with new OTP
            session['reset_otp'] = otp
            session['reset_otp_expiry'] = otp_expiry.isoformat()
            
            if send_password_reset_email(email, otp, f"{user['fname']} {user['lname']}"):
                flash('New OTP sent to your email!', 'success')
            else:
                flash('Error sending OTP. Please try again.', 'error')
        else:
            flash('No account found with this email address.', 'error')
            
    except Exception as e:
        print(f"Resend forgot password OTP error: {e}")
        flash('Error resending OTP. Please try again.', 'error')
    finally:
        conn.close()
    
    return render_template('forgot_password.html', step='verify_otp', email=email)

def send_password_reset_email(email, otp, user_name=""):
    """Send password reset OTP to user's email"""
    try:
        msg = Message(
            subject='1TERA - Password Reset OTP',
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f'''
        Hello {user_name},
        
        Your OTP for password reset is: {otp}
        
        This OTP will expire in 10 minutes.
        
        If you didn't request a password reset, please ignore this email and your account will remain secure.
        
        Stay safe,
        1TERA Team
        '''
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False
    
#error handlers 
@app.errorhandler(404)
def not_found_error(error):
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Page Not Found - 1TERA</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            h1 { color: #2563eb; }
            a { color: #2563eb; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>404 - Page Not Found</h1>
        <p>The page you're looking for doesn't exist.</p>
        <a href="/">Go back to Home</a>
    </body>
    </html>
    """, 404

@app.errorhandler(500)
def internal_error(error):
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Server Error - 1TERA</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            h1 { color: #ef4444; }
            a { color: #2563eb; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>500 - Server Error</h1>
        <p>Something went wrong on our server.</p>
        <a href="/">Go back to Home</a>
    </body>
    </html>
    """, 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 1TERA SYSTEM STARTUP CONFIGURATION")
    print("="*60)
    
    print("📋 BASIC CONFIGURATION:")
    print(f"  SECRET_KEY: {'*' * len(app.config['SECRET_KEY'])} (hidden)")
    print(f"  DEBUG: {DEBUG}")
    print(f"  ENVIRONMENT: {ENVIRONMENT}")
    
    print("\n🗄️  MYSQL DATABASE CONFIGURATION:")
    print(f"  MYSQL_HOST: {app.config['MYSQL_HOST']}")
    print(f"  MYSQL_USER: {app.config['MYSQL_USER']}")
    print(f"  MYSQL_PASSWORD: {'*' * len(app.config['MYSQL_PASSWORD']) if app.config['MYSQL_PASSWORD'] else 'None'} (hidden)")
    print(f"  MYSQL_DB: {app.config['MYSQL_DB']}")
    
    print("\n📧 EMAIL CONFIGURATION:")
    print(f"  MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"  MAIL_PORT: {app.config['MAIL_PORT']}")
    print(f"  MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
    print(f"  MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"  MAIL_PASSWORD: {'*' * len(app.config['MAIL_PASSWORD']) if app.config['MAIL_PASSWORD'] else 'None'} (hidden)")
    print(f"  ADMIN_EMAIL: {app.config['ADMIN_EMAIL']}")
    print(f"  MAIL_SUPPRESS_SEND: {app.config['MAIL_SUPPRESS_SEND']}")
    
    print("\n📁 FILE UPLOAD CONFIGURATION:")
    print(f"  UPLOAD_FOLDER: {app.config['UPLOAD_FOLDER']}")
    print(f"  MAX_CONTENT_LENGTH: {app.config['MAX_CONTENT_LENGTH']} bytes ({app.config['MAX_CONTENT_LENGTH']//(1024*1024)}MB)")
    print(f"  ALLOWED_EXTENSIONS: {ALLOWED_EXTENSIONS}")
    
    print("\n🌐 DEPLOYMENT CONFIGURATION:")
    print(f"  HOST: {HOST}")
    print(f"  PORT: {PORT}")
    
    
    print("="*60)
    print("✅ System ready to start!")
    print("="*60 + "\n")
    
    app.run(host=HOST, port=PORT, debug=DEBUG)