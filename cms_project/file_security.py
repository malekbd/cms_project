"""
Secure File Upload and Media Handling
Provides protection against malicious file uploads and ensures secure media handling.
"""

import os
import magic
import hashlib
import logging
from pathlib import Path
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from .security_utils import InputValidator

logger = logging.getLogger('security')


class SecureFileUpload:
    """
    Handles secure file uploads with validation and sanitization.
    """
    
    # Allowed file extensions for different file types
    ALLOWED_EXTENSIONS = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'],
        'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
        'spreadsheet': ['.xls', '.xlsx', '.csv', '.ods'],
        'archive': ['.zip', '.tar', '.gz', '.7z'],
    }
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZES = {
        'image': 5 * 1024 * 1024,  # 5MB
        'document': 10 * 1024 * 1024,  # 10MB
        'spreadsheet': 10 * 1024 * 1024,  # 10MB
        'archive': 20 * 1024 * 1024,  # 20MB
        'default': 5 * 1024 * 1024,  # 5MB
    }
    
    # Dangerous file extensions to block
    DANGEROUS_EXTENSIONS = [
        '.php', '.php3', '.php4', '.php5', '.php7', '.phtml',
        '.asp', '.aspx', '.ashx', '.asmx',
        '.jsp', '.jspx', '.jsw', '.jsv', '.jspf',
        '.pl', '.pm', '.cgi', '.py', '.pyc', '.pyo', '.pyd',
        '.exe', '.dll', '.so', '.bat', '.cmd', '.sh', '.bin',
        '.js', '.html', '.htm', '.xhtml', '.svg',
        '.vbs', '.vbe', '.wsf', '.wsh', '.ps1', '.psm1',
        '.jar', '.class', '.war', '.ear',
        '.swf', '.fla', '.action',
    ]
    
    # Dangerous MIME types to block
    DANGEROUS_MIME_TYPES = [
        'application/x-php',
        'application/x-httpd-php',
        'text/x-php',
        'application/x-msdownload',
        'application/x-msdos-program',
        'application/x-executable',
        'application/x-shellscript',
        'application/x-sh',
        'application/javascript',
        'text/javascript',
        'application/x-javascript',
    ]
    
    @staticmethod
    def validate_file_upload(uploaded_file: UploadedFile, file_category='image', user=None, request=None):
        """
        Validate a file upload for security.
        
        Args:
            uploaded_file: Django UploadedFile object
            file_category: Type of file ('image', 'document', 'spreadsheet', 'archive')
            user: User uploading the file (for logging)
            request: Request object (for logging)
        
        Returns:
            dict: Validation result with 'is_valid', 'errors', and 'sanitized_filename'
        
        Raises:
            ValidationError: If file is invalid
        """
        errors = []
        
        # Check if file is provided
        if not uploaded_file:
            raise ValidationError("No file provided.")
        
        # Get file information
        original_filename = uploaded_file.name
        file_size = uploaded_file.size
        content_type = uploaded_file.content_type
        
        # 1. Validate file name
        try:
            sanitized_filename = InputValidator.validate_file_upload(
                original_filename, 
                allowed_extensions=SecureFileUpload.ALLOWED_EXTENSIONS.get(file_category, []),
                max_size_mb=SecureFileUpload.MAX_FILE_SIZES.get(file_category, SecureFileUpload.MAX_FILE_SIZES['default']) // (1024 * 1024)
            )
        except ValidationError as e:
            errors.append(str(e))
        
        # 2. Check for dangerous extensions
        file_ext = os.path.splitext(original_filename.lower())[1]
        if file_ext in SecureFileUpload.DANGEROUS_EXTENSIONS:
            errors.append(f"Dangerous file extension: {file_ext}")
        
        # 3. Validate file size
        max_size = SecureFileUpload.MAX_FILE_SIZES.get(file_category, SecureFileUpload.MAX_FILE_SIZES['default'])
        if file_size > max_size:
            errors.append(f"File too large. Maximum size: {max_size // (1024 * 1024)}MB")
        
        # 4. Validate MIME type
        try:
            # Read first 2048 bytes for MIME detection
            file_content = uploaded_file.read(2048)
            uploaded_file.seek(0)  # Reset file pointer
            
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_buffer(file_content)
            
            # Check for dangerous MIME types
            if detected_mime in SecureFileUpload.DANGEROUS_MIME_TYPES:
                errors.append(f"Dangerous file type detected: {detected_mime}")
            
            # Validate MIME type matches extension
            if not SecureFileUpload._mime_matches_extension(detected_mime, file_ext, file_category):
                errors.append(f"File type mismatch. Detected: {detected_mime}, Expected based on extension: {file_ext}")
        
        except Exception as e:
            errors.append(f"Unable to verify file type: {str(e)}")
        
        # 5. Additional validation based on file category
        if file_category == 'image':
            image_errors = SecureFileUpload._validate_image(uploaded_file)
            errors.extend(image_errors)
        
        # 6. Scan for malware patterns (basic pattern matching)
        malware_patterns = SecureFileUpload._scan_for_malware_patterns(uploaded_file)
        if malware_patterns:
            errors.append(f"Potential malware patterns detected: {malware_patterns}")
        
        # Log security event if there are errors
        if errors and request:
            from .security_monitoring import SecurityMonitor
            SecurityMonitor.log_security_event(
                'malicious_file_upload',
                request,
                details={
                    'filename': original_filename,
                    'file_size': file_size,
                    'content_type': content_type,
                    'errors': errors,
                    'user': user.username if user else 'anonymous',
                },
                user=user
            )
        
        if errors:
            raise ValidationError(errors)
        
        # Generate secure filename
        secure_filename = SecureFileUpload._generate_secure_filename(original_filename, user)
        
        return {
            'is_valid': True,
            'sanitized_filename': secure_filename,
            'original_filename': original_filename,
            'file_size': file_size,
            'content_type': content_type,
            'detected_mime': detected_mime if 'detected_mime' in locals() else 'unknown',
        }
    
    @staticmethod
    def _validate_image(uploaded_file):
        """Validate image files for security."""
        errors = []
        
        try:
            # Reset file pointer
            uploaded_file.seek(0)
            
            # Open image with PIL
            image = Image.open(uploaded_file)
            
            # Check image dimensions
            width, height = image.size
            max_dimension = 5000  # Maximum dimension to prevent decompression bombs
            
            if width > max_dimension or height > max_dimension:
                errors.append(f"Image dimensions too large: {width}x{height}. Maximum: {max_dimension}x{max_dimension}")
            
            # Check for decompression bomb (extremely large images)
            # PIL will raise a DecompressionBombError if image is too large
            image.verify()
            
            # Reset file pointer again
            uploaded_file.seek(0)
            
        except Image.DecompressionBombError:
            errors.append("Image is a potential decompression bomb (too large).")
        except Exception as e:
            errors.append(f"Invalid image file: {str(e)}")
        
        return errors
    
    @staticmethod
    def _mime_matches_extension(mime_type, extension, category):
        """Check if MIME type matches file extension."""
        # MIME type to extension mapping
        mime_to_ext = {
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/png': ['.png'],
            'image/gif': ['.gif'],
            'image/bmp': ['.bmp'],
            'image/webp': ['.webp'],
            'image/svg+xml': ['.svg'],
            'application/pdf': ['.pdf'],
            'application/msword': ['.doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
            'text/plain': ['.txt'],
            'text/rtf': ['.rtf'],
            'application/vnd.ms-excel': ['.xls'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            'text/csv': ['.csv'],
            'application/zip': ['.zip'],
            'application/x-tar': ['.tar'],
            'application/gzip': ['.gz'],
        }
        
        # Check if extension is in allowed list for this MIME type
        allowed_extensions = mime_to_ext.get(mime_type, [])
        return extension in allowed_extensions
    
    @staticmethod
    def _scan_for_malware_patterns(uploaded_file):
        """Basic malware pattern scanning."""
        patterns = [
            b'<?php',
            b'eval(',
            b'base64_decode',
            b'gzinflate',
            b'system(',
            b'shell_exec',
            b'exec(',
            b'passthru',
        ]
        
        try:
            # Read file content
            original_position = uploaded_file.tell()
            uploaded_file.seek(0)
            content = uploaded_file.read(4096)  # Read first 4KB
            uploaded_file.seek(original_position)  # Reset position
            
            found_patterns = []
            for pattern in patterns:
                if pattern in content:
                    found_patterns.append(pattern.decode('utf-8', errors='ignore'))
            
            return found_patterns if found_patterns else None
            
        except Exception:
            return None
    
    @staticmethod
    def _generate_secure_filename(original_filename, user=None):
        """Generate a secure filename to prevent path traversal and collisions."""
        # Extract extension
        name, ext = os.path.splitext(original_filename)
        
        # Sanitize filename
        from .security_utils import InputValidator
        sanitized_name = InputValidator.sanitize_path(name)
        
        # Generate hash for uniqueness
        hash_input = f"{sanitized_name}_{user.id if user else 'anonymous'}_{os.urandom(8).hex()}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        # Create secure filename
        secure_name = f"{file_hash}{ext.lower()}"
        
        return secure_name
    
    @staticmethod
    def get_upload_path(instance, filename, subdirectory='uploads'):
        """
        Generate secure upload path for FileField/ImageField.
        Usage: upload_to=lambda instance, filename: SecureFileUpload.get_upload_path(instance, filename, 'logos')
        """
        # Get file extension
        ext = os.path.splitext(filename)[1].lower()
        
        # Generate secure filename
        secure_filename = SecureFileUpload._generate_secure_filename(filename, instance.user if hasattr(instance, 'user') else None)
        
        # Create path based on model and user
        model_name = instance.__class__.__name__.lower()
        user_id = getattr(instance, 'user_id', 'anonymous')
        
        # Return path
        return os.path.join(subdirectory, model_name, str(user_id), secure_filename)


class MediaSecurityMiddleware:
    """
    Middleware to secure media file serving.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers for media files
        if request.path.startswith('/media/'):
            # Prevent media files from being executed as scripts
            response['X-Content-Type-Options'] = 'nosniff'
            
            # Add Content-Disposition header for certain file types
            file_path = request.path.lower()
            dangerous_extensions = ['.html', '.htm', '.svg', '.js', '.php']
            
            if any(file_path.endswith(ext) for ext in dangerous_extensions):
                response['Content-Disposition'] = 'attachment'
            
            # Cache control for media files
            response['Cache-Control'] = 'private, max-age=3600'  # 1 hour cache
        
        return response


def sanitize_media_url(url):
    """
    Sanitize media URLs to prevent path traversal.
    """
    if not url:
        return url
    
    # Remove any attempts at directory traversal
    url = url.replace('../', '').replace('..\\', '')
    
    # Ensure URL starts with /media/
    if not url.startswith('/media/'):
        url = '/media/' + url.lstrip('/')
    
    return url