from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager 
from azure.ai.assistant.management.logger_module import logger
from datetime import datetime
import json
import os
import platform
import random
import re

# This file is auto-generated. Do not edit directly.

# User function: validate_booking_reference
def validate_booking_reference(booking_reference):
    function_config_manager = FunctionConfigManager()
    # Updated pattern to accept uppercase letters (A-Z) and numbers (0-9)
    pattern = r'^[A-Z0-9]{6}$'
    # Check if booking_reference parameter is a string and matches the pattern
    if not isinstance(booking_reference, str) or not re.match(pattern, booking_reference):
        error_message = function_config_manager.get_error_message('invalid_input')
        logger.error(error_message)
        return json.dumps({"function_error": error_message})
    # All validations passed
    return json.dumps({"result": True})

# User function: send_email
def send_email(email_address, reservation_summary, payment_link):
    function_config_manager = FunctionConfigManager()
    try:
        # Simulate sending an email by printing the details (since we can't actually send emails)
        # In a real scenario, here you would use an email service provider API
        email_content = f"To: {email_address}\n\nReservation Summary:\n{reservation_summary}\n\nPayment Link: {payment_link}"
        # Log the simulated email content
        logger.info(f"Email content:\n{email_content}")
        
        # Since it's a simulation, always return success
        result = {
            "email_sent": True,
            "email_address": email_address,
            "reservation_summary": reservation_summary,
            "payment_link": payment_link
        }
        return json.dumps({"result": result})
    except Exception as e:
        error_type = 'generic_error'
        error_message = function_config_manager.get_error_message(error_type)
        logger.error(f"{error_message}: {str(e)}")
        return json.dumps({"function_error": error_message})

# User function: send_sms
def send_sms(phone_number, message):
    function_config_manager = FunctionConfigManager()
    
    try:
        # Emulating SMS sending process; in reality you'd have an API or service call here
        # This is a mock-up of the successful operation.
        # For example, we can log the SMS message as proof of the "sending" operation.
        logger.info(f"Sending SMS to {phone_number}: {message}")
        return json.dumps({"result": f"SMS sent to {phone_number} successfully."})
    except Exception as e:
        error_message = function_config_manager.get_error_message('generic_error')
        logger.error(error_message)
        return json.dumps({"function_error": error_message})

