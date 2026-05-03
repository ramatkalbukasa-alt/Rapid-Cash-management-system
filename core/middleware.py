import logging
from core.models import AgentActivityLog
from decimal import Decimal

logger = logging.getLogger(__name__)

class ActivityLoggingMiddleware:
    """
    Middleware to log agent activities (login, logout, transactions, session open/close)
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/static/',
            '/media/',
            '/admin/jsi18n/',
            '/two_factor/',
        ]

    def __call__(self, request):
        response = self.get_response(request)
        
        # Log user actions if authenticated
        if request.user.is_authenticated:
            self.log_activity(request, response)
        
        return response

    def log_activity(self, request, response):
        """Log activity based on request path and method"""
        path = request.path
        method = request.method
        user = request.user
        
        # Skip exempt paths
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return
        
        try:
            action = None
            
            # Determine action based on path and method
            if 'logout' in path and method == 'GET':
                action = 'LOGOUT'
            elif ('login' in path or 'two_factor' in path) and method == 'POST':
                action = 'LOGIN'
            elif 'open_session' in path or 'caisse/open' in path:
                action = 'SESSION_OPEN'
            elif 'close_session' in path or 'caisse/close' in path:
                action = 'SESSION_CLOSE'
            elif 'process_transaction' in path and method == 'POST':
                action = 'TRANSACTION_CREATE'
            elif 'delete' in path and method == 'POST':
                action = 'TRANSACTION_CANCEL'
            
            # Only log if action was identified
            if action:
                AgentActivityLog.objects.create(
                    agent=user,
                    action=action,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}", exc_info=True)

    @staticmethod
    def get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
