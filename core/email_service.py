# File: email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
import os
from pathlib import Path
import logging
from jinja2 import Template

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailConfig:
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@bitemebuddy.com")
    FROM_NAME = os.getenv("FROM_NAME", "Bite Me Buddy")

class EmailService:
    def __init__(self):
        self.config = EmailConfig()
        self.templates_dir = Path("templates/emails")
        
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email to recipient"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.config.FROM_NAME} <{self.config.FROM_EMAIL}>"
            msg['To'] = to_email
            
            # Attach text and HTML versions
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Connect to SMTP server
            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def load_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Load and render email template"""
        template_path = self.templates_dir / f"{template_name}.html"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as file:
                template_content = file.read()
            
            template = Template(template_content)
            return template.render(**context)
        else:
            # Fallback to basic template
            return self._create_basic_template(context)
    
    def _create_basic_template(self, context: Dict[str, Any]) -> str:
        """Create basic HTML email template"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{context.get('subject', 'Bite Me Buddy')}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: #4CAF50; 
                          color: white; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Bite Me Buddy</h1>
                </div>
                <div class="content">
                    {context.get('content', '')}
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} Bite Me Buddy. All rights reserved.</p>
                    <p>This is an automated email, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    # Specific email templates
    
    def send_welcome_email(self, user_email: str, user_name: str) -> bool:
        """Send welcome email to new user"""
        context = {
            "user_name": user_name,
            "subject": "Welcome to Bite Me Buddy!",
            "content": f"""
                <h2>Welcome {user_name}!</h2>
                <p>Thank you for registering with Bite Me Buddy. We're excited to have you on board!</p>
                <p>You can now:</p>
                <ul>
                    <li>Browse our delicious food options</li>
                    <li>Place orders from multiple services</li>
                    <li>Track your orders in real-time</li>
                    <li>Save your favorite items</li>
                </ul>
                <p>Start ordering now and enjoy delicious food delivered to your doorstep!</p>
                <p><a href="{os.getenv('SITE_URL', 'http://localhost:8000')}" class="button">Start Ordering</a></p>
            """
        }
        
        html_content = self.load_template("welcome", context)
        return self.send_email(user_email, "Welcome to Bite Me Buddy!", html_content)
    
    def send_order_confirmation(self, user_email: str, order_details: Dict[str, Any]) -> bool:
        """Send order confirmation email"""
        context = {
            "user_name": order_details.get("customer_name"),
            "order_number": order_details.get("order_number"),
            "order_total": order_details.get("total_amount"),
            "delivery_address": order_details.get("delivery_address"),
            "estimated_delivery": order_details.get("estimated_delivery"),
            "order_items": order_details.get("items", []),
            "subject": f"Order Confirmed - #{order_details.get('order_number')}",
            "content": f"""
                <h2>Order Confirmed!</h2>
                <p>Hello {order_details.get('customer_name')},</p>
                <p>Your order has been confirmed and is being prepared.</p>
                
                <h3>Order Details:</h3>
                <p><strong>Order Number:</strong> #{order_details.get('order_number')}</p>
                <p><strong>Total Amount:</strong> ₹{order_details.get('total_amount'):,.2f}</p>
                <p><strong>Delivery Address:</strong><br>{order_details.get('delivery_address')}</p>
                <p><strong>Estimated Delivery:</strong> {order_details.get('estimated_delivery')}</p>
                
                <h3>Order Items:</h3>
                <ul>
                    {"".join([f"<li>{item.get('name')} x {item.get('quantity')} - ₹{item.get('price'):,.2f}</li>" 
                             for item in order_details.get('items', [])])}
                </ul>
                
                <p>You can track your order status from your dashboard.</p>
                <p><a href="{os.getenv('SITE_URL', 'http://localhost:8000')}/myorders" class="button">Track Order</a></p>
            """
        }
        
        html_content = self.load_template("order_confirmation", context)
        return self.send_email(user_email, f"Order Confirmed - #{order_details.get('order_number')}", html_content)
    
    def send_password_reset_email(self, user_email: str, reset_token: str, user_name: str) -> bool:
        """Send password reset email"""
        reset_url = f"{os.getenv('SITE_URL', 'http://localhost:8000')}/reset-password?token={reset_token}"
        
        context = {
            "user_name": user_name,
            "reset_url": reset_url,
            "subject": "Reset Your Password - Bite Me Buddy",
            "content": f"""
                <h2>Password Reset Request</h2>
                <p>Hello {user_name},</p>
                <p>We received a request to reset your password. Click the button below to reset your password:</p>
                <p><a href="{reset_url}" class="button">Reset Password</a></p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request a password reset, please ignore this email.</p>
            """
        }
        
        html_content = self.load_template("password_reset", context)
        return self.send_email(user_email, "Reset Your Password - Bite Me Buddy", html_content)
    
    def send_order_status_update(self, user_email: str, order_details: Dict[str, Any]) -> bool:
        """Send order status update email"""
        status_messages = {
            "preparing": "Your order is being prepared",
            "out_for_delivery": "Your order is out for delivery",
            "delivered": "Your order has been delivered",
            "cancelled": "Your order has been cancelled"
        }
        
        status = order_details.get("status")
        message = status_messages.get(status, "Your order status has been updated")
        
        context = {
            "user_name": order_details.get("customer_name"),
            "order_number": order_details.get("order_number"),
            "status": status,
            "message": message,
            "subject": f"Order Update - #{order_details.get('order_number')}",
            "content": f"""
                <h2>Order Status Updated</h2>
                <p>Hello {order_details.get('customer_name')},</p>
                <p><strong>{message}</strong></p>
                <p><strong>Order Number:</strong> #{order_details.get('order_number')}</p>
                <p><strong>Status:</strong> {status.title().replace('_', ' ')}</p>
                {"<p><strong>Delivery OTP:</strong> " + order_details.get('delivery_otp') + "</p>" 
                 if status == "out_for_delivery" else ""}
                <p>You can track your order status from your dashboard.</p>
                <p><a href="{os.getenv('SITE_URL', 'http://localhost:8000')}/myorders" class="button">View Order</a></p>
            """
        }
        
        html_content = self.load_template("order_update", context)
        return self.send_email(
            user_email, 
            f"Order Update - #{order_details.get('order_number')}", 
            html_content
        )
    
    def send_team_assignment_email(
        self, 
        team_member_email: str, 
        team_member_name: str, 
        order_details: Dict[str, Any]
    ) -> bool:
        """Send order assignment email to team member"""
        context = {
            "team_member_name": team_member_name,
            "order_number": order_details.get("order_number"),
            "customer_name": order_details.get("customer_name"),
            "delivery_address": order_details.get("delivery_address"),
            "estimated_delivery": order_details.get("estimated_delivery"),
            "subject": f"New Order Assigned - #{order_details.get('order_number')}",
            "content": f"""
                <h2>New Order Assigned</h2>
                <p>Hello {team_member_name},</p>
                <p>A new order has been assigned to you for delivery.</p>
                
                <h3>Order Details:</h3>
                <p><strong>Order Number:</strong> #{order_details.get('order_number')}</p>
                <p><strong>Customer:</strong> {order_details.get('customer_name')}</p>
                <p><strong>Delivery Address:</strong><br>{order_details.get('delivery_address')}</p>
                <p><strong>Estimated Delivery:</strong> {order_details.get('estimated_delivery')}</p>
                <p><strong>Delivery OTP:</strong> {order_details.get('delivery_otp')}</p>
                
                <p>Please check your dashboard for complete order details.</p>
                <p><a href="{os.getenv('SITE_URL', 'http://localhost:8000')}/team/dashboard" class="button">View Order</a></p>
            """
        }
        
        html_content = self.load_template("team_assignment", context)
        return self.send_email(
            team_member_email, 
            f"New Order Assigned - #{order_details.get('order_number')}", 
            html_content
        )

# Create global instance
email_service = EmailService()
