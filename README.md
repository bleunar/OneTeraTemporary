# 1TERA - Tigbauan Emergency Response Application
A web-based emergency response system for the municipality of Tigbauan, Philippines. This application allows users to report emergencies, view hotlines, track report status, and provides role-based dashboards for municipal officials.


## Features
- **Emergency Reporting**: Users can submit emergency reports with OTP verification.
- **Hotline Directory**: Categorized emergency contact numbers with icons.
- **Role-Based Dashboards**: Separate interfaces for admin, mayor, engineer, barangay officials, MDRRMO, MSWDO, and radio operators.
- **Admin Panel**: Manage reports, users, notifications, and feedback.
- **File Uploads**: Support for image uploads in reports.
- **Email Notifications**: OTP and status updates via email.


## Setup Instructions

1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd terra
   ```

2. **Create a virtual environment**:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Copy `.env.template` to `.env`:
     ```
     cp .env.template .env
     ```
   - Edit `.env` and fill in your actual values for:
     - SECRET_KEY (required for session security)
     - MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB (database connection)
     - MAIL_USERNAME, MAIL_PASSWORD (Gmail SMTP for OTP emails)
     - HOST (server bind address, default: 0.0.0.0)
     - PORT (server port, default: 5000)
     - ENVIRONMENT (development/production, default: production)

5. **Set up the database**:
   - Ensure MySQL is running and create the database specified in `MYSQL_DB`.
   - Import the database schema if provided (not included in this repo).

6. **Run the application**:
   ```
   python app.py
   ```
   The app will run on the configured HOST and PORT (defaults to http://0.0.0.0:5000).


## Technology Stack
- **Backend**: Flask (Python), MySQL
- **Frontend**: HTML, CSS, JavaScript, Jinja2 templates
- **Email**: Flask-Mail with Gmail SMTP
- **Deployment**: Docker, Python virtual environment


## Prerequisites
- Python 3.9 or up
- MySQL Server
- Docker (containerized deployment)
