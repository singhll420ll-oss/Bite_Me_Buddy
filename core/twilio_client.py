import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Optional
import logging

from core.config import settings

logger = logging.getLogger(__name__)

class TwilioClient:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.client = None
        
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
    
    def is_configured(self) -> bool:
        """Check if Twilio is configured"""
        return all([self.account_sid, self.auth_token, self.phone_number]) and self.client is not None
    
    def send_otp_sms(self, phone_number: str, otp: str, order_number: str) -> bool:
        """
        Send OTP via SMS
        Returns: True if sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning("Twilio not configured, SMS not sent")
            return False
        
        try:
            # Format phone number
            if not phone_number.startswith('+'):
                # Assuming Indian numbers
                if phone_number.startswith('0'):
                    phone_number = '+91' + phone_number[1:]
                else:
                    phone_number = '+91' + phone_number
            
            # Create message
            message_body = f"Your Bite Me Buddy delivery OTP is {otp} for order {order_number}. Valid for 5 minutes."
            
            # Send message
            message = self.client.messages.create(
                body=message_body,
                from_=self.phone_number,
                to=phone_number
            )
            
            logger.info(f"SMS sent to {phone_number}, SID: {message.sid}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False
    
    def send_plan_notification(self, phone_number: str, description: str) -> bool:
        """
        Send plan notification via SMS
        """
        if not self.is_configured():
            logger.warning("Twilio not configured, SMS not sent")
            return False
        
        try:
            # Format phone number
            if not phone_number.startswith('+'):
                if phone_number.startswith('0'):
                    phone_number = '+91' + phone_number[1:]
                else:
                    phone_number = '+91' + phone_number
            
            # Create message
            message_body = f"New plan from Bite Me Buddy: {description[:100]}..."
            
            # Send message
            message = self.client.messages.create(
                body=message_body,
                from_=self.phone_number,
                to=phone_number
            )
            
            logger.info(f"Plan notification sent to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send plan notification: {e}")
            return False

# Global Twilio client instance
twilio_client = TwilioClient()
