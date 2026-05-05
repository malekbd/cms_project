"""
Security Utilities for Input Validation and Sanitization
Provides comprehensive protection against common web vulnerabilities.
"""

import re
import html
import json
import logging
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils.encoding import force_str

logger = logging.getLogger(__name__)


class InputValidator:
    """
    Comprehensive input validation and sanitization.
    Protects against XSS, SQL injection, path traversal, and other attacks.
    """
    
    # Regex patterns for validation
    PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone_bd': r'^(?:\+?88)?01[3-9]\d{8}$',
        'username': r'^[a-zA-Z0-9_@.+ -]{3,150}$',
        'password': r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{12,}$',
        'customer_id': r'^[A-Z0-9][A-Z0-9_-]{0,99}$',
        'ip_address': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
        'url': r'^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(:\d+)?(/[^\s]*)?$',
        'filename': r'^[a-zA-Z0-9_\-\.]+$',
        'no_sql_injection': r'^[^;\'\"\\-]+$',
        'no_xss': r'^[^<>\"\']*$',  # Basic XSS prevention
    }
    
    @staticmethod
    def validate_pattern(value, pattern_name, field_name=None):
        """
        Validate value against a named pattern.
        """
        if not value:
            return value
        
        pattern = InputValidator.PATTERNS.get(pattern_name)
        if not pattern:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        if not re.match(pattern, str(value)):
            field_display = field_name or 'field'
            raise ValidationError(
                f"Invalid {field_display} format. Must match pattern: {pattern_name}"
            )
        
        return value
    
    @staticmethod
    def sanitize_html(text, allowed_tags=None):
        """
        Sanitize HTML input to prevent XSS attacks.
        Removes or escapes dangerous HTML/JavaScript.
        """
        if not text:
            return text
        
        # Convert to string
        text = force_str(text)
        
        # If no allowed tags specified, strip all tags
        if allowed_tags is None:
            return strip_tags(text)
        
        # Basic HTML escaping for safety
        text = html.escape(text)
        
        # Allow specific tags (simplified approach)
        # For production, consider using a library like bleach
        return text
    
    @staticmethod
    def sanitize_sql_input(value):
        """
        Basic SQL injection prevention.
        Note: Django's ORM already provides protection, but this adds an extra layer.
        """
        if value is None:
            return value
        
        value = str(value)
        # Remove common SQL injection patterns
        dangerous_patterns = [
            r'(\-\-)|(\#)',  # SQL comments
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b)',
            r'(\b(OR|AND)\s+\d+=\d+)',
            r'(\bWAITFOR\s+DELAY\b)',
            r'(\bSLEEP\s*\(\s*\d+\s*\))',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {value[:50]}...")
                raise ValidationError("Invalid input detected.")
        
        return value
    
    @staticmethod
    def validate_file_upload(filename, allowed_extensions=None, max_size_mb=10):
        """
        Validate file uploads for security.
        """
        if not filename:
            raise ValidationError("No filename provided.")
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValidationError("Invalid filename.")
        
        # Validate file extension
        if allowed_extensions:
            ext = filename.split('.')[-1].lower() if '.' in filename else ''
            if ext not in allowed_extensions:
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        # Note: File size validation should be done separately when file is uploaded
        return filename
    
    @staticmethod
    def validate_json_input(json_string, max_depth=10, max_length=10000):
        """
        Validate JSON input to prevent DoS attacks.
        """
        if not json_string:
            return {}
        
        if len(json_string) > max_length:
            raise ValidationError(f"JSON too large. Maximum length: {max_length}")
        
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {str(e)}")
        
        # Check for circular references or excessive depth
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValidationError(f"JSON depth exceeds maximum of {max_depth}")
            
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
        
        check_depth(data)
        return data
    
    @staticmethod
    def sanitize_path(path):
        """
        Sanitize file paths to prevent directory traversal attacks.
        """
        if not path:
            return path
        
        # Remove directory traversal attempts
        path = re.sub(r'\.\./', '', path)
        path = re.sub(r'\.\.\\', '', path)
        
        # Remove null bytes
        path = path.replace('\x00', '')
        
        # Ensure path doesn't start with / or \
        path = path.lstrip('/').lstrip('\\')
        
        return path
    
    @staticmethod
    def validate_url(url, allowed_domains=None):
        """
        Validate URLs to prevent SSRF and other attacks.
        """
        if not url:
            return url
        
        try:
            parsed = urlparse(url)
            
            # Basic URL validation
            if not parsed.scheme or parsed.scheme not in ['http', 'https']:
                raise ValidationError("URL must use http or https protocol.")
            
            # Domain validation
            if allowed_domains:
                domain = parsed.netloc.lower()
                if not any(domain.endswith(allowed_domain.lower()) for allowed_domain in allowed_domains):
                    raise ValidationError(f"Domain not allowed. Allowed domains: {', '.join(allowed_domains)}")
            
            # Check for dangerous protocols
            dangerous_protocols = ['file', 'gopher', 'jar', 'ftp']
            if parsed.scheme in dangerous_protocols:
                raise ValidationError(f"Dangerous protocol: {parsed.scheme}")
            
            return url
        except Exception as e:
            raise ValidationError(f"Invalid URL: {str(e)}")


class XSSProtectionMiddleware:
    """
    Middleware to add XSS protection headers and validate inputs.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Sanitize GET parameters
        if request.GET:
            sanitized_get = request.GET.copy()
            for key in sanitized_get:
                value = sanitized_get[key]
                if isinstance(value, str):
                    sanitized_get[key] = InputValidator.sanitize_html(value)
            request.GET = sanitized_get
        
        # Sanitize POST parameters (except for CSRF token)
        if request.method == 'POST' and request.POST:
            sanitized_post = request.POST.copy()
            for key in sanitized_post:
                if key != 'csrfmiddlewaretoken':
                    value = sanitized_post[key]
                    if isinstance(value, str):
                        sanitized_post[key] = InputValidator.sanitize_html(value)
            request.POST = sanitized_post
        
        response = self.get_response(request)
        
        # Add XSS protection headers
        response['X-XSS-Protection'] = '1; mode=block'
        
        return response


def validate_user_input(data, validation_rules):
    """
    Generic user input validation function.
    
    Args:
        data: Dictionary of input data
        validation_rules: Dictionary mapping field names to validation rules
    
    Returns:
        Tuple of (is_valid, errors, sanitized_data)
    """
    errors = {}
    sanitized_data = {}
    
    for field, rules in validation_rules.items():
        value = data.get(field)
        
        # Check required fields
        if rules.get('required', False) and (value is None or str(value).strip() == ''):
            errors[field] = f"{field} is required."
            continue
        
        # Skip validation if value is empty and not required
        if value is None or str(value).strip() == '':
            sanitized_data[field] = value
            continue
        
        # Type validation
        expected_type = rules.get('type', 'string')
        try:
            if expected_type == 'integer':
                value = int(value)
            elif expected_type == 'float':
                value = float(value)
            elif expected_type == 'boolean':
                value = bool(value)
            elif expected_type == 'email':
                InputValidator.validate_pattern(value, 'email', field)
            elif expected_type == 'phone':
                InputValidator.validate_pattern(value, 'phone_bd', field)
        except (ValueError, ValidationError) as e:
            errors[field] = str(e)
            continue
        
        # Pattern validation
        if 'pattern' in rules:
            try:
                InputValidator.validate_pattern(value, rules['pattern'], field)
            except ValidationError as e:
                errors[field] = str(e)
                continue
        
        # Length validation
        if 'min_length' in rules and len(str(value)) < rules['min_length']:
            errors[field] = f"{field} must be at least {rules['min_length']} characters."
            continue
        
        if 'max_length' in rules and len(str(value)) > rules['max_length']:
            errors[field] = f"{field} must be at most {rules['max_length']} characters."
            continue
        
        # Sanitization
        if rules.get('sanitize_html', False):
            value = InputValidator.sanitize_html(value)
        
        if rules.get('sanitize_sql', False):
            value = InputValidator.sanitize_sql_input(value)
        
        sanitized_data[field] = value
    
    return len(errors) == 0, errors, sanitized_data