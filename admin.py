from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
import mysql.connector
from flask_mail import Mail, Message
import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
import math
import json
import os
import pytz

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Timezone configuration
MANILA_TZ = pytz.timezone('Asia/Manila')

def send_user_notification(report_id, notification_type, message, admin_name=None):
    """Send notification to user about report status changes"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get user_id from report
        cur.execute("SELECT user_id FROM emergency_reports WHERE id = %s", (report_id,))
        report = cur.fetchone()
        
        if not report or not report['user_id']:
            return False
        
        user_id = report['user_id']
        
        # Create notification in database
        cur.execute("""
            INSERT INTO user_notifications 
            (user_id, report_id, notification_type, title, message, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, report_id, notification_type, 
              f"Report Status Updated", message, datetime.now(MANILA_TZ)))
        
        # Also store in a separate table for push notifications if needed
        cur.execute("""
            INSERT INTO push_notifications 
            (user_id, report_id, title, body, notification_type, created_at, is_sent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, report_id, "1TERA - Status Update", message, 
              notification_type, datetime.now(MANILA_TZ), False))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # In a real implementation, you would integrate with FCM (Firebase Cloud Messaging) here
        # For now, we'll just store the notification in the database
        print(f"Notification sent to user {user_id}: {message}")
        return True
        
    except Exception as e:
        print(f"Error sending user notification: {e}")
        conn.close()
        return False
    
# Admin authentication decorator
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or 'admin_role' not in session:
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Super admin only decorator
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_role' not in session or session.get('admin_role') != 'super_admin':
            flash('Access denied. Super admin privileges required.', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Radio operator only decorator
def radio_operator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_role' not in session or session.get('admin_role') != 'radio_operator':
            flash('Access denied. Radio operator privileges required.', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    """Get database connection"""
    try:
        conn = mysql.connector.connect(
            host= os.environ.get('MYSQL_HOST', 'localhost'),
            user= os.environ.get('MYSQL_USER', 'root'),
            password= os.environ.get('MYSQL_PASSWORD', ''),
            database= os.environ.get('MYSQL_DB', '1tera_system')
        )
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

def send_admin_credentials_email(email, username, password, role_name, full_name):
    """Send admin credentials to email"""
    try:
        from app import mail
        
        msg = Message(
            subject='1TERA - Admin Account Created',
            sender='onetigbauanemergencyresponse@gmail.com',
            recipients=[email]
        )
        
        msg.body = f'''
Your 1TERA Admin Account Has Been Created

Account Details:
- Full Name: {full_name}
- Username: {username}
- Password: {password}
- Role: {role_name.replace('_', ' ').title()}



Security Notice:
- Keep your credentials secure
- Do not share your password
- Log out after each session

If you didn't request this account, please contact the system administrator immediately.

Stay safe,
1TERA Admin Team
'''
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending admin credentials email: {e}")
        return False

def calculate_estimated_time(user_lat, user_lng):
    """Calculate estimated arrival time from Tigbauan Plaza to user location"""
    # Tigbauan Plaza coordinates (central location)
    plaza_lat = 10.6746
    plaza_lng = 122.3765
    
    if not user_lat or not user_lng or user_lat == 0 or user_lng == 0:
        return "Calculating..."
    
    try:
        # Calculate distance using Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        lat1 = math.radians(plaza_lat)
        lat2 = math.radians(float(user_lat))
        delta_lat = math.radians(float(user_lat) - plaza_lat)
        delta_lng = math.radians(float(user_lng) - plaza_lng)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
             math.cos(lat1) * math.cos(lat2) * 
             math.sin(delta_lng/2) * math.sin(delta_lng/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c  # Distance in kilometers
        
        # Calculate time (assuming average speed of 40 km/h in urban areas)
        speed_kmh = 40
        time_hours = distance / speed_kmh
        time_minutes = time_hours * 60
        
        if time_minutes < 5:
            return "Less than 5 minutes"
        elif time_minutes < 10:
            return "5-10 minutes"
        elif time_minutes < 20:
            return "10-20 minutes"
        elif time_minutes < 30:
            return "20-30 minutes"
        else:
            return "30+ minutes"
    except:
        return "Calculating..."

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('admin_login.html')
        
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT au.*, ar.role_name 
                FROM admin_users au 
                JOIN admin_roles ar ON au.role_id = ar.id 
                WHERE au.username = %s AND au.is_active = TRUE
            """, (username,))
            admin = cur.fetchone()
            
            if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password'].encode('utf-8')):
                # Update last login
                cur.execute("UPDATE admin_users SET last_login = %s WHERE id = %s", 
                           (datetime.now(MANILA_TZ), admin['id']))
                
                # Set session
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                session['admin_role'] = admin['role_name']
                session['admin_name'] = admin['full_name']
                
                conn.commit()
                cur.close()
                conn.close()
                
                flash(f'Welcome back, {admin["full_name"]}!', 'success')
                
                # Redirect based on role
                if admin['role_name'] == 'radio_operator':
                    return redirect(url_for('admin.radio_operator_dashboard'))
                else:
                    return redirect(url_for('admin.admin_dashboard'))
            else:
                flash('Invalid username or password', 'error')
                
        except Exception as e:
            print(f"Admin login error: {e}")
            flash('Login error. Please try again.', 'error')
        finally:
            conn.close()
    
    return render_template('admin_login.html')

def get_brgy_reports_distribution():
    """Get emergency reports distribution by barangay"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # List of Tigbauan barangays
        barangays = [
            'Alupidian', 'Atabayan', 'Bagacay', 'Baguingin', 'Bagumbayan', 'Bangkal', 'Bantud',
            'Barangay 1 (Poblacion)', 'Barangay 2 (Poblacion)', 'Barangay 3 (Poblacion)', 
            'Barangay 4 (Poblacion)', 'Barangay 5 (Poblacion)', 'Barangay 6 (Poblacion)',
            'Barangay 7 (Poblacion)', 'Barangay 8 (Poblacion)', 'Barangay 9 (Poblacion)',
            'Barosong', 'Barroc', 'Bitas', 'Bayuco', 'Binaliuan Mayor', 'Binaliuan Menor',
            'Buenavista', 'Bugasongan', 'Buyu-an', 'Canabuan', 'Cansilayan', 'Cordova Norte',
            'Cordova Sur', 'Danao', 'Dapdap', 'Dorong-an', 'Guisian', 'Isawan', 'Isian',
            'Jamog', 'Lanag', 'Linobayan', 'Lubog', 'Nagba', 'Namocon', 'Napnapan Norte',
            'Napnapan Sur', 'Olo Barroc', 'Parara Norte', 'Parara Sur', 'San Rafael',
            'Sermon', 'Sipitan', 'Supa', 'Tan Pael', 'Taro'
        ]
        
        brgy_data = []
        
        for brgy in barangays:
            # Count reports for each barangay (approximate matching based on location field)
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM emergency_reports 
                WHERE location LIKE %s OR location LIKE %s
            """, (f'%{brgy}%', f'%{brgy.split(" ")[0]}%'))
            
            result = cur.fetchone()
            count = result['count'] if result else 0
            
            brgy_data.append({
                'barangay': brgy,
                'count': count
            })
        
        # Sort by count descending
        brgy_data.sort(key=lambda x: x['count'], reverse=True)
        
        cur.close()
        conn.close()
        
        return brgy_data
        
    except Exception as e:
        print(f"Get barangay distribution error: {e}")
        conn.close()
        return []

def get_monthly_dispatch_stats():
    """Get monthly dispatch statistics for the current year"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get dispatch counts by month for current year
        cur.execute("""
            SELECT 
                MONTH(dispatched_at) as month,
                COUNT(*) as dispatch_count,
                emergency_type
            FROM emergency_reports 
            WHERE dispatched_at IS NOT NULL 
            AND YEAR(dispatched_at) = YEAR(CURDATE())
            GROUP BY MONTH(dispatched_at), emergency_type
            ORDER BY month ASC
        """)
        
        monthly_data = cur.fetchall()
        
        # Initialize monthly structure
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Group by emergency type
        emergency_types = ['fire', 'medical', 'natural', 'accident', 'other']
        monthly_stats = {etype: [0] * 12 for etype in emergency_types}
        total_dispatches = [0] * 12
        
        # Fill the data
        for record in monthly_data:
            month_idx = record['month'] - 1
            etype = record['emergency_type']
            count = record['dispatch_count']
            
            if etype in monthly_stats:
                monthly_stats[etype][month_idx] = count
                total_dispatches[month_idx] += count
        
        cur.close()
        conn.close()
        
        return {
            'months': months,
            'emergency_types': monthly_stats,
            'total_dispatches': total_dispatches,
            'current_year': datetime.now(MANILA_TZ).year
        }
        
    except Exception as e:
        print(f"Get monthly dispatch stats error: {e}")
        conn.close()
        return {'months': [], 'emergency_types': {}, 'total_dispatches': [], 'current_year': datetime.now(MANILA_TZ).year}

def process_chart_data(reports_data):
    """Process reports data for chart visualization"""
    import datetime
    from collections import defaultdict
    
    # Initialize data structures
    line_chart_data = defaultdict(lambda: defaultdict(int))
    bar_chart_data = defaultdict(lambda: defaultdict(int))
    
    # Process each report
    for report in reports_data:
        date = report['date']
        count = report['count']
        emergency_type = report['emergency_type']
        status = report['status']
        
        # Line chart data (total reports per day)
        line_chart_data[date]['total'] += count
        
        # Bar chart data (emergency types)
        bar_chart_data[emergency_type]['count'] += count
    
    # Convert to lists for Chart.js
    dates = sorted(line_chart_data.keys())
    line_chart_values = [line_chart_data[date]['total'] for date in dates]
    
    # Emergency types for bar chart
    emergency_types = list(bar_chart_data.keys())
    bar_chart_values = [bar_chart_data[etype]['count'] for etype in emergency_types]
    
    # Get barangay distribution data from actual database
    brgy_data = get_brgy_reports_distribution()
    brgy_names = [item['barangay'] for item in brgy_data[:15]]  # Top 15 barangays
    brgy_counts = [item['count'] for item in brgy_data[:15]]
    
    # Get monthly dispatch stats
    monthly_stats = get_monthly_dispatch_stats()
    
    # Get monthly barangay stats
    monthly_brgy_stats = get_monthly_brgy_stats()
    
    # Get available years
    available_years = get_available_years()
    
    return {
        'line_chart': {
            'labels': [date.strftime('%Y-%m-%d') for date in dates],
            'datasets': [{
                'label': 'Total Reports',
                'data': line_chart_values,
                'borderColor': '#2563eb',
                'backgroundColor': 'rgba(37, 99, 235, 0.1)',
                'tension': 0.4
            }]
        },
        'bar_chart': {
            'labels': [etype.title() for etype in emergency_types],
            'datasets': [{
                'label': 'Emergency Types',
                'data': bar_chart_values,
                'backgroundColor': [
                    '#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6'
                ],
                'borderColor': [
                    '#dc2626', '#d97706', '#059669', '#1d4ed8', '#7c3aed'
                ],
                'borderWidth': 2
            }]
        },
        'brgy_chart': {
            'labels': brgy_names,
            'datasets': [{
                'label': 'Emergency Reports by Barangay',
                'data': brgy_counts,
                'backgroundColor': 'rgba(59, 130, 246, 0.7)',
                'borderColor': 'rgb(59, 130, 246)',
                'borderWidth': 2
            }]
        },
        'monthly_chart': {
            'labels': monthly_stats['months'],
            'datasets': [
                {
                    'label': 'Total Dispatches',
                    'data': monthly_stats['total_dispatches'],
                    'borderColor': 'rgb(239, 68, 68)',
                    'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                    'yAxisID': 'y',
                    'type': 'line',
                    'tension': 0.4,
                    'borderWidth': 3
                },
                {
                    'label': 'Fire',
                    'data': monthly_stats['emergency_types'].get('fire', [0]*12),
                    'backgroundColor': 'rgba(239, 68, 68, 0.7)',
                    'borderColor': 'rgb(239, 68, 68)',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                },
                {
                    'label': 'Medical',
                    'data': monthly_stats['emergency_types'].get('medical', [0]*12),
                    'backgroundColor': 'rgba(59, 130, 246, 0.7)',
                    'borderColor': 'rgb(59, 130, 246)',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                },
                {
                    'label': 'Natural',
                    'data': monthly_stats['emergency_types'].get('natural', [0]*12),
                    'backgroundColor': 'rgba(245, 158, 11, 0.7)',
                    'borderColor': 'rgb(245, 158, 11)',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                },
                {
                    'label': 'Accident',
                    'data': monthly_stats['emergency_types'].get('accident', [0]*12),
                    'backgroundColor': 'rgba(139, 92, 246, 0.7)',
                    'borderColor': 'rgb(139, 92, 246)',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                }
            ],
            'current_year': monthly_stats['current_year']
        },
        'monthly_brgy_chart': {
            'labels': monthly_brgy_stats['months'],
            'barangays': monthly_brgy_stats['barangays'],
            'monthly_stats': monthly_brgy_stats['monthly_stats'],
            'total_reports': monthly_brgy_stats['total_reports'],
            'year': monthly_brgy_stats['year']
        },
        'available_years': available_years
    }

def get_status_color(status, alpha=1):
    """Get color for status"""
    colors = {
        'pending': f'rgba(245, 158, 11, {alpha})',
        'in_progress': f'rgba(59, 130, 246, {alpha})',
        'resolved': f'rgba(16, 185, 129, {alpha})'
    }
    return colors.get(status, f'rgba(107, 114, 128, {alpha})')

@admin_bp.route('/dashboard')
@admin_login_required
def admin_dashboard():
    # Redirect radio operators and MDRRMO to their dedicated dashboards
    if session.get('admin_role') == 'radio_operator':
        return redirect(url_for('admin.radio_operator_dashboard'))
    elif session.get('admin_role') == 'mdrrmo':
        return redirect(url_for('admin.mdrrmo_dashboard'))
    
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('admin_dashboard.html')
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get emergency reports statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total_reports,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_reports,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_reports,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_reports
            FROM emergency_reports
        """)
        stats = cur.fetchone()
        
        # Get recent emergency reports (limited to 5)
        cur.execute("""
            SELECT er.*, u.fname, u.lname, u.phone_num
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            ORDER BY er.created_at DESC
            LIMIT 5
        """)
        recent_reports = cur.fetchall()
        
        # Get emergency types distribution for bar chart
        cur.execute("""
            SELECT emergency_type, COUNT(*) as count
            FROM emergency_reports
            GROUP BY emergency_type
            ORDER BY count DESC
        """)
        emergency_types = cur.fetchall()
        
        # Get today's reports count
        cur.execute("""
            SELECT COUNT(*) as today_reports 
            FROM emergency_reports 
            WHERE DATE(created_at) = CURDATE()
        """)
        today_stats = cur.fetchone()
        
        # Get reports data for charts
        cur.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count,
                emergency_type,
                status
            FROM emergency_reports 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
            GROUP BY DATE(created_at), emergency_type, status
            ORDER BY date ASC
        """)
        reports_data = cur.fetchall()
        
        # Get feedbacks for dashboard
        cur.execute("""
            SELECT f.*, u.fname, u.lname, u.email
            FROM feedback f
            JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
            LIMIT 10
        """)
        feedbacks = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Process data for charts
        chart_data = process_chart_data(reports_data)
        
        return render_template('admin_dashboard.html',
                             stats=stats,
                             recent_reports=recent_reports,
                             emergency_types=emergency_types,
                             today_reports=today_stats['today_reports'] if today_stats else 0,
                             chart_data=chart_data,
                             feedbacks=feedbacks)
        
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        conn.close()
        return render_template('admin_dashboard.html', stats={}, recent_reports=[], emergency_types=[], today_reports=0, chart_data={}, feedbacks=[])

@admin_bp.route('/get_chart_data')
@admin_login_required
def get_chart_data():
    """API endpoint for chart data with filters"""
    period = request.args.get('period', '7days')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Define date ranges based on period
        date_ranges = {
            '7days': 'INTERVAL 7 DAY',
            '30days': 'INTERVAL 30 DAY',
            '90days': 'INTERVAL 90 DAY',
            '1year': 'INTERVAL 1 YEAR'
        }
        
        date_range = date_ranges.get(period, 'INTERVAL 7 DAY')
        
        cur.execute(f"""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count,
                emergency_type,
                status
            FROM emergency_reports 
            WHERE created_at >= DATE_SUB(NOW(), {date_range})
            GROUP BY DATE(created_at), emergency_type, status
            ORDER BY date ASC
        """)
        reports_data = cur.fetchall()
        
        cur.close()
        conn.close()
        
        chart_data = process_chart_data(reports_data)
        
        return jsonify({
            'success': True,
            'chart_data': chart_data,
            'period': period
        })
        
    except Exception as e:
        print(f"Get chart data error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching chart data'})

@admin_bp.route('/get_brgy_data')
@admin_login_required
def get_brgy_data():
    """API endpoint for barangay distribution data"""
    try:
        brgy_data = get_brgy_reports_distribution()
        return jsonify({
            'success': True,
            'brgy_data': brgy_data
        })
    except Exception as e:
        print(f"Get barangay data error: {e}")
        return jsonify({'success': False, 'message': 'Error fetching barangay data'})

@admin_bp.route('/reports')
@admin_login_required
def admin_reports():
    # Redirect radio operators to their dedicated dashboard
    if session.get('admin_role') == 'radio_operator':
        return redirect(url_for('admin.radio_operator_dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('admin_reports.html', reports=[], pagination=None, stats={})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get total count for pagination
        cur.execute("SELECT COUNT(*) as total FROM emergency_reports")
        total = cur.fetchone()['total']
        
        # Get paginated emergency reports with user info
        cur.execute("""
            SELECT er.*, u.fname, u.lname, u.phone_num, u.email
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            ORDER BY er.created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        reports = cur.fetchall()
        
        # Get statistics for the badge
        cur.execute("""
            SELECT 
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_reports
            FROM emergency_reports
        """)
        stats = cur.fetchone()
        
        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
        
        cur.close()
        conn.close()
        
        return render_template('admin_reports.html', 
                             reports=reports, 
                             pagination=pagination,
                             stats=stats)
        
    except Exception as e:
        print(f"Admin reports error: {e}")
        conn.close()
        return render_template('admin_reports.html', reports=[], pagination=None, stats={})

@admin_bp.route('/update_report_status', methods=['POST'])
@admin_login_required
def update_report_status():
    report_id = request.form.get('report_id')
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes', '')
    
    if not report_id or not new_status:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get current status for comparison
        cur.execute("SELECT status, user_id FROM emergency_reports WHERE id = %s", (report_id,))
        report = cur.fetchone()
        
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'})
        
        current_status = report['status']
        user_id = report['user_id']
        
        # First, check if the columns exist
        cur.execute("SHOW COLUMNS FROM emergency_reports LIKE 'admin_notes'")
        admin_notes_exists = cur.fetchone()
        
        cur.execute("SHOW COLUMNS FROM emergency_reports LIKE 'updated_at'")
        updated_at_exists = cur.fetchone()
        
        # Update report status - handle missing columns gracefully
        if admin_notes_exists and updated_at_exists:
            cur.execute("""
                UPDATE emergency_reports 
                SET status = %s, admin_notes = %s, updated_at = %s 
                WHERE id = %s
            """, (new_status, admin_notes, datetime.now(), report_id))
        elif admin_notes_exists:
            cur.execute("""
                UPDATE emergency_reports 
                SET status = %s, admin_notes = %s
                WHERE id = %s
            """, (new_status, admin_notes, report_id))
        elif updated_at_exists:
            cur.execute("""
                UPDATE emergency_reports 
                SET status = %s, updated_at = %s 
                WHERE id = %s
            """, (new_status, datetime.now(), report_id))
        else:
            cur.execute("""
                UPDATE emergency_reports 
                SET status = %s
                WHERE id = %s
            """, (new_status, report_id))
        
        # Send notification to user if status changed AND user_id exists
        if current_status != new_status and user_id:
            status_messages = {
                'pending': 'is pending review',
                'in_progress': 'is now in progress - help is on the way!',
                'resolved': 'has been resolved'
            }
            
            message = f"Your emergency report {status_messages.get(new_status, 'status has been updated')}"
            if admin_notes:
                message += f". Note: {admin_notes}"
            
            # Create notification in database
            cur.execute("""
                INSERT INTO user_notifications 
                (user_id, report_id, notification_type, title, message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, report_id, new_status, 
                  f"Report Status Updated", message, datetime.now(MANILA_TZ)))
            
            # Also store in push notifications table
            cur.execute("""
                INSERT INTO push_notifications 
                (user_id, report_id, title, body, notification_type, created_at, is_sent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, report_id, "1TERA - Status Update", message, 
                  new_status, datetime.now(MANILA_TZ), False))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Status updated successfully'})
        
    except Exception as e:
        print(f"Update report status error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating status'})
    
@admin_bp.route('/management')
@admin_login_required
@super_admin_required
def admin_management():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('admin_management.html', admins=[], roles=[])
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get all admin users with roles
        cur.execute("""
            SELECT au.*, ar.role_name 
            FROM admin_users au 
            JOIN admin_roles ar ON au.role_id = ar.id
            ORDER BY au.created_at DESC
        """)
        admins = cur.fetchall()
        
        # Get all roles
        cur.execute("SELECT * FROM admin_roles ORDER BY role_name")
        roles = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return render_template('admin_management.html', admins=admins, roles=roles)
        
    except Exception as e:
        print(f"Admin management error: {e}")
        conn.close()
        return render_template('admin_management.html', admins=[], roles=[])

@admin_bp.route('/create_admin', methods=['POST'])
@admin_login_required
@super_admin_required
def create_admin():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    role_id = request.form.get('role_id')
    phone_number = request.form.get('phone_number')
    
    if not all([username, email, password, full_name, role_id]):
        flash('Please fill all required fields', 'error')
        return redirect(url_for('admin.admin_management'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.admin_management'))
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Check if username or email already exists
        cur.execute("SELECT id FROM admin_users WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone():
            flash('Username or email already exists', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('admin.admin_management'))
        
        # Get role name for email
        cur.execute("SELECT role_name FROM admin_roles WHERE id = %s", (role_id,))
        role = cur.fetchone()
        
        if not role:
            flash('Invalid role selected', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('admin.admin_management'))
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert new admin
        cur.execute("""
            INSERT INTO admin_users (username, email, password, role_id, full_name, phone_number)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, email, hashed_password, role_id, full_name, phone_number))
        
        # Send credentials email
        if send_admin_credentials_email(email, username, password, role['role_name'], full_name):
            flash('Admin account created successfully. Credentials sent to email.', 'success')
        else:
            flash('Admin account created but failed to send email.', 'warning')
        
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for('admin.admin_management'))
        
    except Exception as e:
        print(f"Create admin error: {e}")
        flash('Error creating admin account', 'error')
        conn.close()
        return redirect(url_for('admin.admin_management'))

@admin_bp.route('/toggle_admin/<int:admin_id>')
@admin_login_required
@super_admin_required
def toggle_admin(admin_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.admin_management'))
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get current status
        cur.execute("SELECT is_active FROM admin_users WHERE id = %s", (admin_id,))
        admin = cur.fetchone()
        
        if admin:
            new_status = not admin['is_active']
            cur.execute("UPDATE admin_users SET is_active = %s WHERE id = %s", (new_status, admin_id))
            
            status_text = "activated" if new_status else "deactivated"
            flash(f'Admin account {status_text} successfully', 'success')
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Toggle admin error: {e}")
        flash('Error updating admin status', 'error')
        conn.close()
    
    return redirect(url_for('admin.admin_management'))

@admin_bp.route('/send_alert', methods=['POST'])
@admin_login_required
def send_alert():
    """Allow both super_admin and radio_operator to send alerts"""
    if session.get('admin_role') not in ['super_admin', 'radio_operator']:
        return jsonify({'success': False, 'message': 'Insufficient permissions'})
    
    alert_message = request.form.get('alert_message')
    alert_type = request.form.get('alert_type', 'info')
    
    if not alert_message:
        return jsonify({'success': False, 'message': 'Please enter an alert message'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        
        # Store alert in database
        cur.execute("""
            INSERT INTO admin_alerts (message, alert_type, created_by, created_at)
            VALUES (%s, %s, %s, %s)
        """, (alert_message, alert_type, session['admin_id'], datetime.now(MANILA_TZ)))
        
        alert_id = cur.lastrowid
        
        # Send notification to ALL active users
        cur.execute("SELECT id FROM users WHERE id IS NOT NULL")
        users = cur.fetchall()
        
        notification_title = "Emergency Alert from 1TERA"
        if alert_type == 'danger':
            notification_title = "🚨 EMERGENCY ALERT - 1TERA"
        elif alert_type == 'warning':
            notification_title = "⚠️ IMPORTANT NOTICE - 1TERA"
        
        for user in users:
            user_id = user[0]
            # Create notification for each user
            cur.execute("""
                INSERT INTO user_notifications 
                (user_id, notification_type, title, message, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, f'alert_{alert_type}', notification_title, alert_message, datetime.now(MANILA_TZ)))
            
            # Also store for push notifications
            cur.execute("""
                INSERT INTO push_notifications 
                (user_id, title, body, notification_type, created_at, is_sent)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, notification_title, alert_message, f'alert_{alert_type}', datetime.now(MANILA_TZ), False))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Alert sent successfully to all users!'})
        
    except Exception as e:
        print(f"Send alert error: {e}")
        return jsonify({'success': False, 'message': 'Error sending alert'})

@admin_bp.route('/dispatch_response', methods=['POST'])
@admin_login_required
def dispatch_response():
    report_id = request.form.get('report_id')
    response_type = request.form.get('response_type')
    notes = request.form.get('notes', '')
    
    if not report_id or not response_type:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get report location for ETA calculation and user_id
        cur.execute("SELECT latitude, longitude, user_id FROM emergency_reports WHERE id = %s", (report_id,))
        report = cur.fetchone()
        
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'})
        
        estimated_arrival = "Calculating..."
        if report and report['latitude'] and report['longitude']:
            estimated_arrival = calculate_estimated_time(report['latitude'], report['longitude'])
        else:
            estimated_arrival = "Location data unavailable"
        
        # Update the report with dispatch information and automatically set status to in_progress
        update_query = """
            UPDATE emergency_reports 
            SET status = 'in_progress', 
                response_type = %s, 
                estimated_arrival = %s,
                dispatched_at = %s,
                updated_at = %s
        """
        update_params = [response_type, estimated_arrival, datetime.now(), datetime.now()]
        
        # admin_notes if provided
        if notes:
            cur.execute("SHOW COLUMNS FROM emergency_reports LIKE 'admin_notes'")
            if cur.fetchone():
                update_query += ", admin_notes = %s"
                update_params.append(notes)
        
        update_query += " WHERE id = %s"
        update_params.append(report_id)
        
        cur.execute(update_query, update_params)
        
        # Send notification to user if user_id exists
        if report['user_id']:
            response_types = {
                'fire': 'Fire truck',
                'medical': 'Ambulance', 
                'police': 'Police unit',
                'rescue': 'Rescue team'
            }
            
            message = f"{response_types.get(response_type, 'Emergency response')} has been dispatched! Estimated arrival: {estimated_arrival}"
            if notes:
                message += f". Notes: {notes}"
            
            # Create notification in database
            cur.execute("""
                INSERT INTO user_notifications 
                (user_id, report_id, notification_type, title, message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (report['user_id'], report_id, 'dispatched', 
                  "Response Dispatched", message, datetime.now()))
            
            # Also store in push notifications table
            cur.execute("""
                INSERT INTO push_notifications 
                (user_id, report_id, title, body, notification_type, created_at, is_sent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (report['user_id'], report_id, "1TERA - Response Dispatched", message, 
                  'dispatched', datetime.now(), False))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Response dispatched successfully! Estimated arrival: {estimated_arrival}'
        })
        
    except Exception as e:
        print(f"Dispatch response error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error dispatching response'})

@admin_bp.route('/get_report_details/<int:report_id>')
@admin_login_required
def get_report_details(report_id):
    """Get detailed information for a specific report"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT er.*, u.fname, u.lname, u.phone_num, u.email
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.id = %s
        """, (report_id,))
        report = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if report:
            return jsonify({'success': True, 'report': report})
        else:
            return jsonify({'success': False, 'message': 'Report not found'})
            
    except Exception as e:
        print(f"Get report details error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching report details'})

@admin_bp.route('/get_radio_report_details/<int:report_id>')
@admin_login_required
@radio_operator_required
def get_radio_report_details(report_id):
    """Get detailed information for a specific report for radio operator"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT er.*, u.fname, u.lname, u.phone_num, u.email
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.id = %s
        """, (report_id,))
        report = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if report:
            return jsonify({'success': True, 'report': report})
        else:
            return jsonify({'success': False, 'message': 'Report not found'})
            
    except Exception as e:
        print(f"Get radio report details error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching report details'})

@admin_bp.route('/mark_notification_read_for_report/<int:report_id>')
@admin_login_required
def mark_notification_read_for_report(report_id):
    """Mark all notifications for a specific report as read"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        
        # Update emergency_reports table to mark as viewed or update status
        # This is a simplified implementation - you might need to adjust based on your notification system
        cur.execute("""
            UPDATE emergency_reports 
            SET status = 'in_progress', updated_at = %s 
            WHERE id = %s AND status = 'pending'
        """, (datetime.now(), report_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notifications marked as read for report'})
        
    except Exception as e:
        print(f"Mark notification read for report error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating notifications'})
    
@admin_bp.route('/users_feedback')
@admin_login_required
def admin_users_feedback():
    """User Feedbacks Management Page"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('admin_users_feedback.html', feedbacks=[])
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get all feedbacks with user info
        cur.execute("""
            SELECT f.*, u.fname, u.lname, u.email
            FROM feedback f
            JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
        """)
        feedbacks = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return render_template('admin_users_feedback.html', feedbacks=feedbacks)
        
    except Exception as e:
        print(f"Admin users feedback error: {e}")
        conn.close()
        return render_template('admin_users_feedback.html', feedbacks=[])

@admin_bp.route('/mayor_dashboard')
@admin_login_required
def mayor_dashboard():
    return render_template('mayor_dashboard.html')

@admin_bp.route('/engr_dashboard')
@admin_login_required
def engr_dashboard():
    return render_template('engr_dashboard.html')

@admin_bp.route('/brgy_dashboard')
@admin_login_required
def brgy_dashboard():
    return render_template('brgy_dashboard.html')

@admin_bp.route('/mswdo_dashboard')
@admin_login_required
def mswdo_dashboard():
    return render_template('mswdo_dashboard.html')

@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('admin_role', None)
    session.pop('admin_name', None)
    flash('Admin logged out successfully', 'success')
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/get_feedbacks')
@admin_login_required
def get_feedbacks():
    """Get user feedbacks for dashboard"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get recent feedbacks
        cur.execute("""
            SELECT f.*, u.fname, u.lname, u.email
            FROM feedback f
            JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
            LIMIT 5
        """)
        feedbacks = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'feedbacks': feedbacks
        })
        
    except Exception as e:
        print(f"Get feedbacks error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching feedbacks'})

@admin_bp.route('/get_notifications')
@admin_login_required
def get_notifications():
    """Get notifications for admin from emergency_reports table - only unread/pending ones"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get only active emergency reports (pending status) as notifications
        cur.execute("""
            SELECT 
                er.id,
                er.emergency_type,
                er.status,
                er.location,
                er.description,
                er.created_at,
                u.fname,
                u.lname,
                u.phone_num,
                'danger' as notification_type,
                CONCAT(
                    '🚨 ', 
                    UPPER(er.emergency_type), 
                    ' Emergency - ', 
                    er.location
                ) as title,
                CONCAT(
                    'Reported by: ', 
                    u.fname, ' ', u.lname,
                    ' • ', 
                    COALESCE(er.description, 'No description provided'),
                    ' • Phone: ',
                    COALESCE(u.phone_num, 'N/A')
                ) as message
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.status = 'pending'  -- Only show pending reports as notifications
            AND er.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY er.created_at DESC
            LIMIT 20
        """)
        
        emergency_notifications = cur.fetchall()
        
        # Format the notifications for the frontend
        formatted_notifications = []
        for notification in emergency_notifications:
            formatted_notifications.append({
                'id': notification['id'],
                'title': notification['title'],
                'message': notification['message'],
                'type': notification['notification_type'],
                'created_at': notification['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'report_id': notification['id'],
                'emergency_type': notification['emergency_type'],
                'status': notification['status'],
                'location': notification['location'],
                'is_emergency_report': True,
                'reporter_name': f"{notification['fname']} {notification['lname']}",
                'reporter_phone': notification['phone_num']
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'notifications': formatted_notifications
        })
        
    except Exception as e:
        print(f"Get notifications error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching notifications'})
    
@admin_bp.route('/mark_notification_read/<int:notification_id>')
@admin_login_required
def mark_notification_read(notification_id):
    """Mark notification as read by updating the emergency report status"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
        
    except Exception as e:
        print(f"Mark notification read error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating notification'})

def create_emergency_notification(report_id, admin_id, action_type, details):
    """Create notification for emergency report actions"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get report details
        cur.execute("""
            SELECT er.emergency_type, er.location, u.fname, u.lname
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.id = %s
        """, (report_id,))
        report = cur.fetchone()
        
        if report:
            title = f"Emergency Report #{report_id} - {action_type.title()}"
            message = f"{report['emergency_type'].title()} emergency at {report['location']} {action_type} by admin"
            
            # Store in admin_notifications table if it exists
            cur.execute("SHOW TABLES LIKE 'admin_notifications'")
            if cur.fetchone():
                cur.execute("""
                    INSERT INTO admin_notifications (admin_id, title, message, type, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (admin_id, title, message, 'info', datetime.now()))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Create emergency notification error: {e}")
        conn.close()
        return False

@admin_bp.route('/get_unread_notifications_count')
@admin_login_required
def get_unread_notifications_count():
    """Get count of unread notifications (recent emergency reports)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'count': 0})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Count recent emergency reports from last 24 hours
        cur.execute("""
            SELECT COUNT(*) as count
            FROM emergency_reports 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            AND status IN ('pending', 'in_progress')
        """)
        
        result = cur.fetchone()
        count = result['count'] if result else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': count
        })
        
    except Exception as e:
        print(f"Get unread notifications count error: {e}")
        conn.close()
        return jsonify({'success': False, 'count': 0})
    
@admin_bp.route('/radio_operator_dashboard')
@admin_login_required
@radio_operator_required
def radio_operator_dashboard():
    """Radio Operator Dashboard - Focused on emergency response"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('radio_operator_dashboard.html', 
                             active_reports=[], 
                             hotlines=[], 
                             stats={},
                             today_reports=0)
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get active emergency reports (pending and in progress)
        cur.execute("""
            SELECT er.*, u.fname, u.lname, u.phone_num, u.email
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.status IN ('pending', 'in_progress')
            ORDER BY 
                CASE WHEN er.status = 'pending' THEN 1 ELSE 2 END,
                er.created_at DESC
        """)
        active_reports = cur.fetchall()
        
        # Get statistics for the dashboard
        cur.execute("""
            SELECT 
                COUNT(*) as total_reports,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_reports,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_reports,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_reports
            FROM emergency_reports
        """)
        stats = cur.fetchone()
        
        # Get today's reports count
        cur.execute("""
            SELECT COUNT(*) as today_reports 
            FROM emergency_reports 
            WHERE DATE(created_at) = CURDATE()
        """)
        today_stats = cur.fetchone()
        
        # Get emergency hotlines
        cur.execute("SHOW TABLES LIKE 'hotlines'")
        if cur.fetchone():
            cur.execute("SELECT * FROM hotlines ORDER BY category, name")
        else:
            cur.execute("SELECT * FROM hotlines ORDER BY category, name")
        hotlines = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return render_template('radio_operator_dashboard.html', 
                             active_reports=active_reports, 
                             hotlines=hotlines,
                             stats=stats,
                             today_reports=today_stats['today_reports'] if today_stats else 0)
        
    except Exception as e:
        print(f"Radio operator dashboard error: {e}")
        conn.close()
        return render_template('radio_operator_dashboard.html', 
                             active_reports=[], 
                             hotlines=[], 
                             stats={},
                             today_reports=0)

@admin_bp.route('/mdrrmo_dashboard')
@admin_login_required
def mdrrmo_dashboard():
    """MDRRMO Dashboard - Full emergency management access"""
    # Redirect to admin dashboard since MDRRMO has similar access to super_admin but without admin management
    return redirect(url_for('admin.admin_dashboard'))

# Update the admin_login function to handle MDRRMO role
@admin_bp.route('/login', methods=['GET', 'POST'], endpoint='admin_login_route')
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('admin_login.html')
        
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT au.*, ar.role_name 
                FROM admin_users au 
                JOIN admin_roles ar ON au.role_id = ar.id 
                WHERE au.username = %s AND au.is_active = TRUE
            """, (username,))
            admin = cur.fetchone()
            
            if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password'].encode('utf-8')):
                # Update last login
                cur.execute("UPDATE admin_users SET last_login = %s WHERE id = %s", 
                           (datetime.now(MANILA_TZ), admin['id']))
                
                # Set session
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                session['admin_role'] = admin['role_name']
                session['admin_name'] = admin['full_name']
                
                conn.commit()
                cur.close()
                conn.close()
                
                flash(f'Welcome back, {admin["full_name"]}!', 'success')
                
                # Redirect based on role
                if admin['role_name'] == 'radio_operator':
                    return redirect(url_for('admin.radio_operator_dashboard'))
                elif admin['role_name'] == 'mdrrmo':
                    return redirect(url_for('admin.mdrrmo_dashboard'))
                else:
                    return redirect(url_for('admin.admin_dashboard'))
            else:
                flash('Invalid username or password', 'error')
                
        except Exception as e:
            print(f"Admin login error: {e}")
            flash('Login error. Please try again.', 'error')
        finally:
            conn.close()
    
    return render_template('admin_login.html')

@admin_bp.route('/notification_click/<int:report_id>')
@admin_login_required
def notification_click(report_id):
    """Handle notification click and redirect to emergency report"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.admin_reports'))
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Verify report exists
        cur.execute("SELECT id FROM emergency_reports WHERE id = %s", (report_id,))
        report = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if report:
            # Redirect to reports page and focus on this specific report
            return redirect(url_for('admin.admin_reports') + f'#report-{report_id}')
        else:
            flash('Report not found', 'error')
            return redirect(url_for('admin.admin_reports'))
            
    except Exception as e:
        print(f"Notification click error: {e}")
        conn.close()
        return redirect(url_for('admin.admin_reports'))

@admin_bp.route('/get_report_by_id/<int:report_id>')
@admin_login_required
def get_report_by_id(report_id):
    """Get specific report data for highlighting"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT er.*, u.fname, u.lname, u.phone_num, u.email
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.id = %s
        """, (report_id,))
        report = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if report:
            return jsonify({'success': True, 'report': report})
        else:
            return jsonify({'success': False, 'message': 'Report not found'})
            
    except Exception as e:
        print(f"Get report by ID error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching report'})

@admin_bp.route('/mark_report_viewed/<int:report_id>')
@admin_login_required
def mark_report_viewed(report_id):
    """Mark report as viewed by admin (optional)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor()
        

        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Report marked as viewed'})
        
    except Exception as e:
        print(f"Mark report viewed error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating report'})
    
@admin_bp.route('/get_heatmap_data')
@admin_login_required
def get_heatmap_data():
    """Get heatmap data for all emergency reports with coordinates"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get all emergency reports with coordinates
        cur.execute("""
            SELECT 
                er.id,
                er.emergency_type,
                er.status,
                er.latitude,
                er.longitude,
                er.location,
                er.description,
                er.created_at,
                er.e_img,
                CONCAT(COALESCE(u.fname, ''), ' ', COALESCE(u.lname, '')) as user_name,
                u.phone_num
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.latitude IS NOT NULL 
            AND er.longitude IS NOT NULL
            AND er.latitude != 0 
            AND er.longitude != 0
            ORDER BY er.created_at DESC
        """)
        
        reports = cur.fetchall()
        
        report_data = []
        for report in reports:
            # Parse coordinates safely
            try:
                lat = float(report['latitude']) if report['latitude'] else None
                lng = float(report['longitude']) if report['longitude'] else None
            except (TypeError, ValueError):
                lat = None
                lng = None
            
            if lat and lng:
                report_data.append({
                    'id': report['id'],
                    'emergency_type': report['emergency_type'],
                    'status': report['status'],
                    'latitude': lat,
                    'longitude': lng,
                    'location': report['location'],
                    'description': report['description'],
                    'created_at': report['created_at'].isoformat() if report['created_at'] else None,
                    'user_name': report['user_name'].strip() or 'Anonymous',
                    'phone_num': report['phone_num'],
                    'image': report['e_img']
                })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'reports': report_data,
            'total': len(report_data)
        })
        
    except Exception as e:
        print(f"Error getting heatmap data: {e}")
        if conn:
            conn.close()
        return jsonify({
            'success': False,
            'message': 'Error loading heatmap data'
        })

@admin_bp.route('/get_heatmap_stats')
@admin_login_required
def get_heatmap_stats():
    """Get statistics for heatmap dashboard"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Total emergencies with coordinates
        cur.execute("""
            SELECT COUNT(*) as total 
            FROM emergency_reports 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
            AND latitude != 0 
            AND longitude != 0
        """)
        total_result = cur.fetchone()
        total = total_result['total'] if total_result else 0
        
        # Active emergencies (pending + in_progress)
        cur.execute("""
            SELECT COUNT(*) as active 
            FROM emergency_reports 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
            AND latitude != 0 
            AND longitude != 0
            AND status IN ('pending', 'in_progress')
        """)
        active_result = cur.fetchone()
        active = active_result['active'] if active_result else 0
        
        # Resolved emergencies
        cur.execute("""
            SELECT COUNT(*) as resolved 
            FROM emergency_reports 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
            AND latitude != 0 
            AND longitude != 0
            AND status = 'resolved'
        """)
        resolved_result = cur.fetchone()
        resolved = resolved_result['resolved'] if resolved_result else 0
        
        # Today's emergencies
        cur.execute("""
            SELECT COUNT(*) as today 
            FROM emergency_reports 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
            AND latitude != 0 
            AND longitude != 0
            AND DATE(created_at) = CURDATE()
        """)
        today_result = cur.fetchone()
        today = today_result['today'] if today_result else 0
        
        # Emergency type distribution
        cur.execute("""
            SELECT emergency_type, COUNT(*) as count
            FROM emergency_reports 
            WHERE latitude IS NOT NULL 
            AND longitude IS NOT NULL
            AND latitude != 0 
            AND longitude != 0
            GROUP BY emergency_type
            ORDER BY count DESC
        """)
        type_distribution = cur.fetchall()
        
        # Recent emergencies (last 24 hours)
        cur.execute("""
            SELECT 
                er.id,
                er.emergency_type,
                er.status,
                er.location,
                er.description,
                er.created_at,
                CONCAT(COALESCE(u.fname, ''), ' ', COALESCE(u.lname, '')) as user_name
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.latitude IS NOT NULL 
            AND er.longitude IS NOT NULL
            AND er.latitude != 0 
            AND er.longitude != 0
            AND er.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY er.created_at DESC
            LIMIT 10
        """)
        recent_emergencies = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'active': active,
                'resolved': resolved,
                'today': today
            },
            'type_distribution': type_distribution,
            'recent_emergencies': recent_emergencies
        })
        
    except Exception as e:
        print(f"Error getting heatmap stats: {e}")
        if conn:
            conn.close()
        return jsonify({
            'success': False,
            'message': 'Error loading heatmap statistics'
        })

@admin_bp.route('/get_emergencies_by_type/<emergency_type>')
@admin_login_required
def get_emergencies_by_type(emergency_type):
    """Get emergencies filtered by type"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        if emergency_type == 'all':
            cur.execute("""
                SELECT 
                    er.id,
                    er.emergency_type,
                    er.status,
                    er.latitude,
                    er.longitude,
                    er.location,
                    er.description,
                    er.created_at,
                    CONCAT(COALESCE(u.fname, ''), ' ', COALESCE(u.lname, '')) as user_name
                FROM emergency_reports er
                LEFT JOIN users u ON er.user_id = u.id
                WHERE er.latitude IS NOT NULL 
                AND er.longitude IS NOT NULL
                AND er.latitude != 0 
                AND er.longitude != 0
                ORDER BY er.created_at DESC
            """)
        else:
            cur.execute("""
                SELECT 
                    er.id,
                    er.emergency_type,
                    er.status,
                    er.latitude,
                    er.longitude,
                    er.location,
                    er.description,
                    er.created_at,
                    CONCAT(COALESCE(u.fname, ''), ' ', COALESCE(u.lname, '')) as user_name
                FROM emergency_reports er
                LEFT JOIN users u ON er.user_id = u.id
                WHERE er.emergency_type = %s
                AND er.latitude IS NOT NULL 
                AND er.longitude IS NOT NULL
                AND er.latitude != 0 
                AND er.longitude != 0
                ORDER BY er.created_at DESC
            """, (emergency_type,))
        
        reports = cur.fetchall()
        
        report_data = []
        for report in reports:
            try:
                lat = float(report['latitude']) if report['latitude'] else None
                lng = float(report['longitude']) if report['longitude'] else None
            except (TypeError, ValueError):
                lat = None
                lng = None
            
            if lat and lng:
                report_data.append({
                    'id': report['id'],
                    'emergency_type': report['emergency_type'],
                    'status': report['status'],
                    'latitude': lat,
                    'longitude': lng,
                    'location': report['location'],
                    'description': report['description'],
                    'created_at': report['created_at'].isoformat() if report['created_at'] else None,
                    'user_name': report['user_name'].strip() or 'Anonymous'
                })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'reports': report_data,
            'count': len(report_data),
            'type': emergency_type
        })
        
    except Exception as e:
        print(f"Error getting emergencies by type: {e}")
        if conn:
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error loading {emergency_type} emergencies'
        })

@admin_bp.route('/get_emergency_details/<int:report_id>')
@admin_login_required
def get_emergency_details(report_id):
    """Get detailed information for a specific emergency report"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        cur.execute("""
            SELECT 
                er.*,
                CONCAT(COALESCE(u.fname, ''), ' ', COALESCE(u.lname, '')) as user_name,
                u.phone_num,
                u.email,
                au.full_name as responded_by_name
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            LEFT JOIN admin_users au ON er.responded_by = au.id
            WHERE er.id = %s
        """, (report_id,))
        
        report = cur.fetchone()
        
        if not report:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Emergency report not found'})
        
        # Format response data
        report_data = {
            'id': report['id'],
            'emergency_type': report['emergency_type'],
            'status': report['status'],
            'location': report['location'],
            'description': report['description'],
            'latitude': float(report['latitude']) if report['latitude'] else None,
            'longitude': float(report['longitude']) if report['longitude'] else None,
            'created_at': report['created_at'].isoformat() if report['created_at'] else None,
            'user_name': report['user_name'].strip() if report['user_name'] else 'Anonymous',
            'phone_num': report['phone_num'],
            'email': report['email'],
            'image': report['e_img'],
            'response_type': report['response_type'],
            'estimated_arrival': report['estimated_arrival'],
            'admin_notes': report['admin_notes'],
            'dispatched_at': report['dispatched_at'].isoformat() if report['dispatched_at'] else None,
            'responded_by': report['responded_by_name']
        }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'report': report_data
        })
        
    except Exception as e:
        print(f"Error getting emergency details: {e}")
        if conn:
            conn.close()
        return jsonify({
            'success': False,
            'message': 'Error loading emergency details'
        })

@admin_bp.route('/update_emergency_status', methods=['POST'])
@admin_login_required
def update_emergency_status():
    """Update emergency report status from heatmap"""
    report_id = request.form.get('report_id')
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes', '')
    
    if not report_id or not new_status:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get current status and user_id for notification
        cur.execute("SELECT status, user_id FROM emergency_reports WHERE id = %s", (report_id,))
        report = cur.fetchone()
        
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'})
        
        current_status = report['status']
        user_id = report['user_id']
        
        # Update report status
        cur.execute("""
            UPDATE emergency_reports 
            SET status = %s, admin_notes = %s, updated_at = %s 
            WHERE id = %s
        """, (new_status, admin_notes, datetime.now(MANILA_TZ), report_id))
        
        # Send notification to user if status changed
        if current_status != new_status and user_id:
            status_messages = {
                'pending': 'is pending review',
                'in_progress': 'is now in progress - help is on the way!',
                'resolved': 'has been resolved'
            }
            
            message = f"Your emergency report {status_messages.get(new_status, 'status has been updated')}"
            if admin_notes:
                message += f". Note: {admin_notes}"
            
            # Create notification
            cur.execute("""
                INSERT INTO user_notifications 
                (user_id, report_id, notification_type, title, message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, report_id, new_status, "Report Status Updated", message, datetime.now(MANILA_TZ)))
            
            # Store for push notifications
            cur.execute("""
                INSERT INTO push_notifications 
                (user_id, report_id, title, body, notification_type, created_at, is_sent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, report_id, "1TERA - Status Update", message, new_status, datetime.now(MANILA_TZ), False))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Status updated successfully'
        })
        
    except Exception as e:
        print(f"Update emergency status error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'message': 'Error updating status'})

@admin_bp.route('/get_barangay_heatmap_data')
@admin_login_required
def get_barangay_heatmap_data():
    """Get heatmap data aggregated by barangay"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # List of Tigbauan barangays
        barangays = [
            'Alupidian', 'Atabayan', 'Bagacay', 'Baguingin', 'Bagumbayan', 'Bangkal', 'Bantud',
            'Barangay 1 (Poblacion)', 'Barangay 2 (Poblacion)', 'Barangay 3 (Poblacion)', 
            'Barangay 4 (Poblacion)', 'Barangay 5 (Poblacion)', 'Barangay 6 (Poblacion)',
            'Barangay 7 (Poblacion)', 'Barangay 8 (Poblacion)', 'Barangay 9 (Poblacion)',
            'Barosong', 'Barroc', 'Bitas', 'Bayuco', 'Binaliuan Mayor', 'Binaliuan Menor',
            'Buenavista', 'Bugasongan', 'Buyu-an', 'Canabuan', 'Cansilayan', 'Cordova Norte',
            'Cordova Sur', 'Danao', 'Dapdap', 'Dorong-an', 'Guisian', 'Isawan', 'Isian',
            'Jamog', 'Lanag', 'Linobayan', 'Lubog', 'Nagba', 'Namucon', 'Napnapan Norte',
            'Napnapan Sur', 'Olo Barroc', 'Parara Norte', 'Parara Sur', 'San Rafael',
            'Sermon', 'Sipitan', 'Supa', 'Tan Pael', 'Taro'
        ]
        
        barangay_data = []
        
        for brgy in barangays:
            # Count reports for each barangay (approximate matching)
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM emergency_reports 
                WHERE (location LIKE %s OR location LIKE %s)
                AND latitude IS NOT NULL 
                AND longitude IS NOT NULL
            """, (f'%{brgy}%', f'%{brgy.split(" ")[0]}%'))
            
            result = cur.fetchone()
            count = result['count'] if result else 0
            
            # Get approximate coordinates for barangay center
            # These would ideally be stored in a separate table
            brgy_coords = get_barangay_coordinates(brgy)
            
            if brgy_coords and count > 0:
                barangay_data.append({
                    'barangay': brgy,
                    'count': count,
                    'latitude': brgy_coords['lat'],
                    'longitude': brgy_coords['lng'],
                    'intensity': min(count / 10.0, 1.0)  # Normalize intensity
                })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'barangay_data': barangay_data
        })
        
    except Exception as e:
        print(f"Error getting barangay heatmap data: {e}")
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': 'Error loading barangay data'})

def get_barangay_coordinates(barangay_name):
    """Get approximate coordinates for barangay centers"""
    # This is a simplified mapping - in production, you'd want a proper database table
    barangay_coords = {
        'Barangay 1 (Poblacion)': {'lat': 10.6746, 'lng': 122.3765},
        'Barangay 2 (Poblacion)': {'lat': 10.6750, 'lng': 122.3770},
        'Barangay 3 (Poblacion)': {'lat': 10.6755, 'lng': 122.3775},
        'Barangay 4 (Poblacion)': {'lat': 10.6760, 'lng': 122.3780},
        'Barangay 5 (Poblacion)': {'lat': 10.6765, 'lng': 122.3785},
        'Barangay 6 (Poblacion)': {'lat': 10.6770, 'lng': 122.3790},
        'Barangay 7 (Poblacion)': {'lat': 10.6775, 'lng': 122.3795},
        'Barangay 8 (Poblacion)': {'lat': 10.6780, 'lng': 122.3800},
        'Barangay 9 (Poblacion)': {'lat': 10.6785, 'lng': 122.3805},
        'Alupidian': {'lat': 10.7005, 'lng': 122.3897},
        'Atabayan': {'lat': 10.6900, 'lng': 122.3900},
        'Bagacay': {'lat': 10.6800, 'lng': 122.3950},
        # more barangay coordinates as needed
    }
    
    return barangay_coords.get(barangay_name, {'lat': 10.6747, 'lng': 122.3964})  # Default to Tigbauan center

@admin_bp.route('/export_heatmap_data')
@admin_login_required
def export_heatmap_data():
    """Export heatmap data as CSV"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        cur.execute("""
            SELECT 
                er.id,
                er.emergency_type,
                er.status,
                er.latitude,
                er.longitude,
                er.location,
                er.description,
                er.created_at,
                CONCAT(COALESCE(u.fname, ''), ' ', COALESCE(u.lname, '')) as user_name,
                u.phone_num
            FROM emergency_reports er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE er.latitude IS NOT NULL 
            AND er.longitude IS NOT NULL
            AND er.latitude != 0 
            AND er.longitude != 0
            ORDER BY er.created_at DESC
        """)
        
        reports = cur.fetchall()
        
        # Generate CSV content
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Emergency Type', 'Status', 'Latitude', 'Longitude', 
            'Location', 'Description', 'Created At', 'User Name', 'Phone Number'
        ])
        
        # Write data
        for report in reports:
            writer.writerow([
                report['id'],
                report['emergency_type'],
                report['status'],
                report['latitude'],
                report['longitude'],
                report['location'] or '',
                report['description'] or '',
                report['created_at'].strftime('%Y-%m-%d %H:%M:%S') if report['created_at'] else '',
                report['user_name'].strip() if report['user_name'] else 'Anonymous',
                report['phone_num'] or ''
            ])
        
        cur.close()
        conn.close()
        
        from flask import Response
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=emergency_heatmap_data.csv"}
        )
        
    except Exception as e:
        print(f"Error exporting heatmap data: {e}")
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': 'Error exporting data'})
    
def get_brgy_reports_distribution():
    """Get emergency reports distribution by barangay from actual database data"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get actual barangays from reports in the database
        cur.execute("""
            SELECT 
                CASE 
                    WHEN location LIKE '%Alupidian%' THEN 'Alupidian'
                    WHEN location LIKE '%Atabayan%' THEN 'Atabayan'
                    WHEN location LIKE '%Bagacay%' THEN 'Bagacay'
                    WHEN location LIKE '%Baguingin%' THEN 'Baguingin'
                    WHEN location LIKE '%Bagumbayan%' THEN 'Bagumbayan'
                    WHEN location LIKE '%Bangkal%' THEN 'Bangkal'
                    WHEN location LIKE '%Bantud%' THEN 'Bantud'
                    WHEN location LIKE '%Barangay 1%' OR location LIKE '%Poblacion%' THEN 'Barangay 1 (Poblacion)'
                    WHEN location LIKE '%Barangay 2%' THEN 'Barangay 2 (Poblacion)'
                    WHEN location LIKE '%Barangay 3%' THEN 'Barangay 3 (Poblacion)'
                    WHEN location LIKE '%Barangay 4%' THEN 'Barangay 4 (Poblacion)'
                    WHEN location LIKE '%Barangay 5%' THEN 'Barangay 5 (Poblacion)'
                    WHEN location LIKE '%Barangay 6%' THEN 'Barangay 6 (Poblacion)'
                    WHEN location LIKE '%Barangay 7%' THEN 'Barangay 7 (Poblacion)'
                    WHEN location LIKE '%Barangay 8%' THEN 'Barangay 8 (Poblacion)'
                    WHEN location LIKE '%Barangay 9%' THEN 'Barangay 9 (Poblacion)'
                    WHEN location LIKE '%Barosong%' THEN 'Barosong'
                    WHEN location LIKE '%Barroc%' THEN 'Barroc'
                    WHEN location LIKE '%Bitas%' THEN 'Bitas'
                    WHEN location LIKE '%Bayuco%' THEN 'Bayuco'
                    WHEN location LIKE '%Binaliuan Mayor%' THEN 'Binaliuan Mayor'
                    WHEN location LIKE '%Binaliuan Menor%' THEN 'Binaliuan Menor'
                    WHEN location LIKE '%Buenavista%' THEN 'Buenavista'
                    WHEN location LIKE '%Bugasongan%' THEN 'Bugasongan'
                    WHEN location LIKE '%Buyu-an%' THEN 'Buyu-an'
                    WHEN location LIKE '%Canabuan%' THEN 'Canabuan'
                    WHEN location LIKE '%Cansilayan%' THEN 'Cansilayan'
                    WHEN location LIKE '%Cordova Norte%' THEN 'Cordova Norte'
                    WHEN location LIKE '%Cordova Sur%' THEN 'Cordova Sur'
                    WHEN location LIKE '%Danao%' THEN 'Danao'
                    WHEN location LIKE '%Dapdap%' THEN 'Dapdap'
                    WHEN location LIKE '%Dorong-an%' THEN 'Dorong-an'
                    WHEN location LIKE '%Guisian%' THEN 'Guisian'
                    WHEN location LIKE '%Isawan%' THEN 'Isawan'
                    WHEN location LIKE '%Isian%' THEN 'Isian'
                    WHEN location LIKE '%Jamog%' THEN 'Jamog'
                    WHEN location LIKE '%Lanag%' THEN 'Lanag'
                    WHEN location LIKE '%Linobayan%' THEN 'Linobayan'
                    WHEN location LIKE '%Lubog%' THEN 'Lubog'
                    WHEN location LIKE '%Nagba%' THEN 'Nagba'
                    WHEN location LIKE '%Namocon%' THEN 'Namocon'
                    WHEN location LIKE '%Napnapan Norte%' THEN 'Napnapan Norte'
                    WHEN location LIKE '%Napnapan Sur%' THEN 'Napnapan Sur'
                    WHEN location LIKE '%Olo Barroc%' THEN 'Olo Barroc'
                    WHEN location LIKE '%Parara Norte%' THEN 'Parara Norte'
                    WHEN location LIKE '%Parara Sur%' THEN 'Parara Sur'
                    WHEN location LIKE '%San Rafael%' THEN 'San Rafael'
                    WHEN location LIKE '%Sermon%' THEN 'Sermon'
                    WHEN location LIKE '%Sipitan%' THEN 'Sipitan'
                    WHEN location LIKE '%Supa%' THEN 'Supa'
                    WHEN location LIKE '%Tan Pael%' THEN 'Tan Pael'
                    WHEN location LIKE '%Taro%' THEN 'Taro'
                    ELSE 'Other Areas'
                END as barangay,
                COUNT(*) as count
            FROM emergency_reports 
            WHERE location IS NOT NULL AND location != ''
            GROUP BY barangay
            HAVING barangay != 'Other Areas'
            ORDER BY count DESC
        """)
        
        brgy_data = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return brgy_data
        
    except Exception as e:
        print(f"Get barangay distribution error: {e}")
        conn.close()
        return []

def get_monthly_brgy_stats(year=None):
    """Get monthly barangay statistics for a specific year"""
    if not year:
        year = datetime.now(MANILA_TZ).year
    
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get monthly counts by barangay for the specified year
        cur.execute("""
            SELECT 
                MONTH(created_at) as month,
                CASE 
                    WHEN location LIKE '%Alupidian%' THEN 'Alupidian'
                    WHEN location LIKE '%Atabayan%' THEN 'Atabayan'
                    WHEN location LIKE '%Bagacay%' THEN 'Bagacay'
                    WHEN location LIKE '%Baguingin%' THEN 'Baguingin'
                    WHEN location LIKE '%Bagumbayan%' THEN 'Bagumbayan'
                    WHEN location LIKE '%Bangkal%' THEN 'Bangkal'
                    WHEN location LIKE '%Bantud%' THEN 'Bantud'
                    WHEN location LIKE '%Barangay 1%' OR location LIKE '%Poblacion%' THEN 'Barangay 1 (Poblacion)'
                    WHEN location LIKE '%Barangay 2%' THEN 'Barangay 2 (Poblacion)'
                    WHEN location LIKE '%Barangay 3%' THEN 'Barangay 3 (Poblacion)'
                    WHEN location LIKE '%Barangay 4%' THEN 'Barangay 4 (Poblacion)'
                    WHEN location LIKE '%Barangay 5%' THEN 'Barangay 5 (Poblacion)'
                    WHEN location LIKE '%Barangay 6%' THEN 'Barangay 6 (Poblacion)'
                    WHEN location LIKE '%Barangay 7%' THEN 'Barangay 7 (Poblacion)'
                    WHEN location LIKE '%Barangay 8%' THEN 'Barangay 8 (Poblacion)'
                    WHEN location LIKE '%Barangay 9%' THEN 'Barangay 9 (Poblacion)'
                    WHEN location LIKE '%Barosong%' THEN 'Barosong'
                    WHEN location LIKE '%Barroc%' THEN 'Barroc'
                    WHEN location LIKE '%Bitas%' THEN 'Bitas'
                    WHEN location LIKE '%Bayuco%' THEN 'Bayuco'
                    WHEN location LIKE '%Binaliuan Mayor%' THEN 'Binaliuan Mayor'
                    WHEN location LIKE '%Binaliuan Menor%' THEN 'Binaliuan Menor'
                    WHEN location LIKE '%Buenavista%' THEN 'Buenavista'
                    WHEN location LIKE '%Bugasongan%' THEN 'Bugasongan'
                    WHEN location LIKE '%Buyu-an%' THEN 'Buyu-an'
                    WHEN location LIKE '%Canabuan%' THEN 'Canabuan'
                    WHEN location LIKE '%Cansilayan%' THEN 'Cansilayan'
                    WHEN location LIKE '%Cordova Norte%' THEN 'Cordova Norte'
                    WHEN location LIKE '%Cordova Sur%' THEN 'Cordova Sur'
                    WHEN location LIKE '%Danao%' THEN 'Danao'
                    WHEN location LIKE '%Dapdap%' THEN 'Dapdap'
                    WHEN location LIKE '%Dorong-an%' THEN 'Dorong-an'
                    WHEN location LIKE '%Guisian%' THEN 'Guisian'
                    WHEN location LIKE '%Isawan%' THEN 'Isawan'
                    WHEN location LIKE '%Isian%' THEN 'Isian'
                    WHEN location LIKE '%Jamog%' THEN 'Jamog'
                    WHEN location LIKE '%Lanag%' THEN 'Lanag'
                    WHEN location LIKE '%Linobayan%' THEN 'Linobayan'
                    WHEN location LIKE '%Lubog%' THEN 'Lubog'
                    WHEN location LIKE '%Nagba%' THEN 'Nagba'
                    WHEN location LIKE '%Namocon%' THEN 'Namocon'
                    WHEN location LIKE '%Napnapan Norte%' THEN 'Napnapan Norte'
                    WHEN location LIKE '%Napnapan Sur%' THEN 'Napnapan Sur'
                    WHEN location LIKE '%Olo Barroc%' THEN 'Olo Barroc'
                    WHEN location LIKE '%Parara Norte%' THEN 'Parara Norte'
                    WHEN location LIKE '%Parara Sur%' THEN 'Parara Sur'
                    WHEN location LIKE '%San Rafael%' THEN 'San Rafael'
                    WHEN location LIKE '%Sermon%' THEN 'Sermon'
                    WHEN location LIKE '%Sipitan%' THEN 'Sipitan'
                    WHEN location LIKE '%Supa%' THEN 'Supa'
                    WHEN location LIKE '%Tan Pael%' THEN 'Tan Pael'
                    WHEN location LIKE '%Taro%' THEN 'Taro'
                    ELSE 'Other Areas'
                END as barangay,
                COUNT(*) as count
            FROM emergency_reports 
            WHERE YEAR(created_at) = %s
                AND location IS NOT NULL 
                AND location != ''
            GROUP BY MONTH(created_at), barangay
            HAVING barangay != 'Other Areas'
            ORDER BY month ASC, count DESC
        """, (year,))
        
        monthly_data = cur.fetchall()
        
        # Initialize monthly structure
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Get unique barangays
        cur.execute("""
            SELECT DISTINCT
                CASE 
                    WHEN location LIKE '%Alupidian%' THEN 'Alupidian'
                    WHEN location LIKE '%Atabayan%' THEN 'Atabayan'
                    WHEN location LIKE '%Bagacay%' THEN 'Bagacay'
                    WHEN location LIKE '%Baguingin%' THEN 'Baguingin'
                    WHEN location LIKE '%Bagumbayan%' THEN 'Bagumbayan'
                    WHEN location LIKE '%Bangkal%' THEN 'Bangkal'
                    WHEN location LIKE '%Bantud%' THEN 'Bantud'
                    WHEN location LIKE '%Barangay 1%' OR location LIKE '%Poblacion%' THEN 'Barangay 1 (Poblacion)'
                    WHEN location LIKE '%Barangay 2%' THEN 'Barangay 2 (Poblacion)'
                    WHEN location LIKE '%Barangay 3%' THEN 'Barangay 3 (Poblacion)'
                    WHEN location LIKE '%Barangay 4%' THEN 'Barangay 4 (Poblacion)'
                    WHEN location LIKE '%Barangay 5%' THEN 'Barangay 5 (Poblacion)'
                    WHEN location LIKE '%Barangay 6%' THEN 'Barangay 6 (Poblacion)'
                    WHEN location LIKE '%Barangay 7%' THEN 'Barangay 7 (Poblacion)'
                    WHEN location LIKE '%Barangay 8%' THEN 'Barangay 8 (Poblacion)'
                    WHEN location LIKE '%Barangay 9%' THEN 'Barangay 9 (Poblacion)'
                    WHEN location LIKE '%Barosong%' THEN 'Barosong'
                    WHEN location LIKE '%Barroc%' THEN 'Barroc'
                    WHEN location LIKE '%Bitas%' THEN 'Bitas'
                    WHEN location LIKE '%Bayuco%' THEN 'Bayuco'
                    WHEN location LIKE '%Binaliuan Mayor%' THEN 'Binaliuan Mayor'
                    WHEN location LIKE '%Binaliuan Menor%' THEN 'Binaliuan Menor'
                    WHEN location LIKE '%Buenavista%' THEN 'Buenavista'
                    WHEN location LIKE '%Bugasongan%' THEN 'Bugasongan'
                    WHEN location LIKE '%Buyu-an%' THEN 'Buyu-an'
                    WHEN location LIKE '%Canabuan%' THEN 'Canabuan'
                    WHEN location LIKE '%Cansilayan%' THEN 'Cansilayan'
                    WHEN location LIKE '%Cordova Norte%' THEN 'Cordova Norte'
                    WHEN location LIKE '%Cordova Sur%' THEN 'Cordova Sur'
                    WHEN location LIKE '%Danao%' THEN 'Danao'
                    WHEN location LIKE '%Dapdap%' THEN 'Dapdap'
                    WHEN location LIKE '%Dorong-an%' THEN 'Dorong-an'
                    WHEN location LIKE '%Guisian%' THEN 'Guisian'
                    WHEN location LIKE '%Isawan%' THEN 'Isawan'
                    WHEN location LIKE '%Isian%' THEN 'Isian'
                    WHEN location LIKE '%Jamog%' THEN 'Jamog'
                    WHEN location LIKE '%Lanag%' THEN 'Lanag'
                    WHEN location LIKE '%Linobayan%' THEN 'Linobayan'
                    WHEN location LIKE '%Lubog%' THEN 'Lubog'
                    WHEN location LIKE '%Nagba%' THEN 'Nagba'
                    WHEN location LIKE '%Namocon%' THEN 'Namocon'
                    WHEN location LIKE '%Napnapan Norte%' THEN 'Napnapan Norte'
                    WHEN location LIKE '%Napnapan Sur%' THEN 'Napnapan Sur'
                    WHEN location LIKE '%Olo Barroc%' THEN 'Olo Barroc'
                    WHEN location LIKE '%Parara Norte%' THEN 'Parara Norte'
                    WHEN location LIKE '%Parara Sur%' THEN 'Parara Sur'
                    WHEN location LIKE '%San Rafael%' THEN 'San Rafael'
                    WHEN location LIKE '%Sermon%' THEN 'Sermon'
                    WHEN location LIKE '%Sipitan%' THEN 'Sipitan'
                    WHEN location LIKE '%Supa%' THEN 'Supa'
                    WHEN location LIKE '%Tan Pael%' THEN 'Tan Pael'
                    WHEN location LIKE '%Taro%' THEN 'Taro'
                    ELSE 'Other Areas'
                END as barangay
            FROM emergency_reports 
            WHERE YEAR(created_at) = %s
                AND location IS NOT NULL 
                AND location != ''
            HAVING barangay != 'Other Areas'
            ORDER BY barangay
        """, (year,))
        
        barangays = [row['barangay'] for row in cur.fetchall()]
        
        # Initialize data structure
        monthly_stats = {brgy: [0] * 12 for brgy in barangays}
        total_reports = [0] * 12
        
        # Fill the data
        for record in monthly_data:
            month_idx = record['month'] - 1
            brgy = record['barangay']
            count = record['count']
            
            if brgy in monthly_stats:
                monthly_stats[brgy][month_idx] = count
                total_reports[month_idx] += count
        
        cur.close()
        conn.close()
        
        return {
            'months': months,
            'barangays': barangays,
            'monthly_stats': monthly_stats,
            'total_reports': total_reports,
            'year': year
        }
        
    except Exception as e:
        print(f"Get monthly barangay stats error: {e}")
        conn.close()
        return {'months': [], 'barangays': [], 'monthly_stats': {}, 'total_reports': [], 'year': year}

def get_available_years():
    """Get available years from emergency reports"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT YEAR(created_at) as year FROM emergency_reports ORDER BY year DESC")
        years = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return years
    except Exception as e:
        print(f"Get available years error: {e}")
        conn.close()
        return [datetime.now(MANILA_TZ).year]
    
@admin_bp.route('/get_monthly_brgy_data')
@admin_login_required
def get_monthly_brgy_data():
    """API endpoint for monthly barangay data with year filter"""
    year = request.args.get('year', datetime.now(MANILA_TZ).year, type=int)
    
    try:
        monthly_brgy_stats = get_monthly_brgy_stats(year)
        available_years = get_available_years()
        
        return jsonify({
            'success': True,
            'monthly_brgy_data': monthly_brgy_stats,
            'available_years': available_years
        })
    except Exception as e:
        print(f"Get monthly barangay data error: {e}")
        return jsonify({'success': False, 'message': 'Error fetching monthly barangay data'})

@admin_bp.route('/get_monthly_dispatch_data')
@admin_login_required
def get_monthly_dispatch_data():
    """API endpoint for monthly dispatch data with year filter"""
    year = request.args.get('year', datetime.now(MANILA_TZ).year, type=int)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get dispatch counts by month for specified year
        cur.execute("""
            SELECT 
                MONTH(dispatched_at) as month,
                COUNT(*) as dispatch_count,
                emergency_type
            FROM emergency_reports 
            WHERE dispatched_at IS NOT NULL 
            AND YEAR(dispatched_at) = %s
            GROUP BY MONTH(dispatched_at), emergency_type
            ORDER BY month ASC
        """, (year,))
        
        monthly_data = cur.fetchall()
        
        # Initialize monthly structure
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Group by emergency type
        emergency_types = ['fire', 'medical', 'natural', 'accident', 'other']
        monthly_stats = {etype: [0] * 12 for etype in emergency_types}
        total_dispatches = [0] * 12
        
        # Fill the data
        for record in monthly_data:
            month_idx = record['month'] - 1
            etype = record['emergency_type']
            count = record['dispatch_count']
            
            if etype in monthly_stats:
                monthly_stats[etype][month_idx] = count
                total_dispatches[month_idx] += count
        
        cur.close()
        conn.close()
        
        available_years = get_available_years()
        
        return jsonify({
            'success': True,
            'monthly_data': {
                'months': months,
                'emergency_types': monthly_stats,
                'total_dispatches': total_dispatches,
                'year': year
            },
            'available_years': available_years
        })
        
    except Exception as e:
        print(f"Get monthly dispatch data error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Error fetching monthly dispatch data'})

@admin_bp.route('/download_chart_data')
@admin_login_required
def download_chart_data():
    """Download chart data as CSV"""
    chart_type = request.args.get('type', '')
    year = request.args.get('year', datetime.now(MANILA_TZ).year, type=int)
    
    if not chart_type:
        return jsonify({'success': False, 'message': 'Chart type required'})
    
    try:
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        if chart_type == 'monthly_dispatch':
            monthly_data = get_monthly_dispatch_stats(year)
            writer.writerow(['Month', 'Total Dispatches', 'Fire', 'Medical', 'Natural Disaster', 'Accident', 'Other'])
            
            for i, month in enumerate(monthly_data['months']):
                writer.writerow([
                    month,
                    monthly_data['total_dispatches'][i],
                    monthly_data['emergency_types'].get('fire', [0]*12)[i],
                    monthly_data['emergency_types'].get('medical', [0]*12)[i],
                    monthly_data['emergency_types'].get('natural', [0]*12)[i],
                    monthly_data['emergency_types'].get('accident', [0]*12)[i],
                    monthly_data['emergency_types'].get('other', [0]*12)[i]
                ])
                
            filename = f'emergency_dispatch_report_{year}.csv'
            
        elif chart_type == 'monthly_barangay':
            monthly_brgy_data = get_monthly_brgy_stats(year)
            # Write header
            header = ['Month'] + monthly_brgy_data['barangays'] + ['Total']
            writer.writerow(header)
            
            # Write data
            for i, month in enumerate(monthly_brgy_data['months']):
                row = [month]
                for brgy in monthly_brgy_data['barangays']:
                    row.append(monthly_brgy_data['monthly_stats'].get(brgy, [0]*12)[i])
                row.append(monthly_brgy_data['total_reports'][i])
                writer.writerow(row)
                
            filename = f'barangay_reports_{year}.csv'
            
        elif chart_type == 'barangay_distribution':
            brgy_data = get_brgy_reports_distribution()
            writer.writerow(['Barangay', 'Number of Reports'])
            
            for item in brgy_data:
                writer.writerow([item['barangay'], item['count']])
                
            filename = 'barangay_distribution.csv'
            
        else:
            return jsonify({'success': False, 'message': 'Invalid chart type'})
        
        from flask import Response
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        print(f"Download chart data error: {e}")
        return jsonify({'success': False, 'message': 'Error downloading data'})