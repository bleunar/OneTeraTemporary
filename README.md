# 1TERA - Tigbauan Emergency Response Application
A web-based emergency response system for the municipality of Tigbauan, Philippines. This application allows users to report emergencies, view hotlines, track report status, and provides role-based dashboards for municipal officials.


## Features
- **Emergency Reporting**: Users can submit emergency reports with OTP verification.
- **Hotline Directory**: Categorized emergency contact numbers with icons.
- **Role-Based Dashboards**: Separate interfaces for admin, mayor, engineer, barangay officials, MDRRMO, MSWDO, and radio operators.
- **Admin Panel**: Manage reports, users, notifications, and feedback.
- **File Uploads**: Support for image uploads in reports.
- **Email Notifications**: OTP and status updates via email.


## Technology Stack
- **Backend**: Flask (Python), MySQL
- **Frontend**: HTML, CSS, JavaScript, Jinja2 templates
- **Email**: Flask-Mail with Gmail SMTP
- **Deployment**: Docker, Python virtual environment


## Prerequisites
- Python 3.9 or up
- MySQL Server
- Docker (containerized deployment)
