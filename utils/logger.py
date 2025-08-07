"""
Advanced Logging System for OpenBullet Python
Provides comprehensive logging with file rotation, filtering, and multiple outputs
"""

import logging
import logging.handlers
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading
from enum import Enum

class LogLevel(Enum):
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG

class LogFormat(Enum):
    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"
    COLORED = "colored"

class Logger:
    """
    Advanced logging system with file rotation, filtering,
    and multiple output handlers
    """
    
    def __init__(self, 
                 name: str = "OpenBullet",
                 log_dir: str = "logs",
                 level: LogLevel = LogLevel.INFO,
                 format_type: LogFormat = LogFormat.DETAILED,
                 max_file_size: int = 10*1024*1024,  # 10MB
                 backup_count: int = 5):
        
        self.name = name
        self.log_dir = Path(log_dir)
        self.level = level
        self.format_type = format_type
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Create log directory
        self.log_dir.mkdir(exist_ok=True)
        
        # Initialize loggers
        self.main_logger = logging.getLogger(name)
        self.main_logger.setLevel(level.value)
        
        # Clear existing handlers
        self.main_logger.handlers.clear()
        
        # Statistics
        self.stats = {
            'total_logs': 0,
            'error_count': 0,
            'warning_count': 0,
            'info_count': 0,
            'debug_count': 0
        }
        
        # Thread lock for thread-safe logging
        self.lock = threading.Lock()
        
        # Setup handlers
        self._setup_handlers()
        
        # Custom filters
        self.filters = {}
        
    def _setup_handlers(self):
        """Setup logging handlers"""
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level.value)
        console_handler.setFormatter(self._get_formatter(self.format_type))
        self.main_logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / f"{self.name.lower()}.log",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # File gets all levels
        file_handler.setFormatter(self._get_formatter(LogFormat.DETAILED))
        self.main_logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / f"{self.name.lower()}_errors.log",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(self._get_formatter(LogFormat.DETAILED))
        self.main_logger.addHandler(error_handler)
        
        # JSON handler for structured logs
        json_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / f"{self.name.lower()}_structured.json",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(self._get_formatter(LogFormat.JSON))
        self.main_logger.addHandler(json_handler)
        
    def _get_formatter(self, format_type: LogFormat) -> logging.Formatter:
        """Get formatter based on format type"""
        if format_type == LogFormat.SIMPLE:
            return logging.Formatter('%(levelname)s: %(message)s')
            
        elif format_type == LogFormat.DETAILED:
            return logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
        elif format_type == LogFormat.COLORED:
            return ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
        elif format_type == LogFormat.JSON:
            return JsonFormatter()
            
        else:
            return logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            
    def debug(self, message: str, extra: Optional[Dict] = None):
        """Log debug message"""
        with self.lock:
            self.stats['total_logs'] += 1
            self.stats['debug_count'] += 1
            self.main_logger.debug(message, extra=extra or {})
            
    def info(self, message: str, extra: Optional[Dict] = None):
        """Log info message"""
        with self.lock:
            self.stats['total_logs'] += 1
            self.stats['info_count'] += 1
            self.main_logger.info(message, extra=extra or {})
            
    def warning(self, message: str, extra: Optional[Dict] = None):
        """Log warning message"""
        with self.lock:
            self.stats['total_logs'] += 1
            self.stats['warning_count'] += 1
            self.main_logger.warning(message, extra=extra or {})
            
    def error(self, message: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Log error message"""
        with self.lock:
            self.stats['total_logs'] += 1
            self.stats['error_count'] += 1
            self.main_logger.error(message, extra=extra or {}, exc_info=exc_info)
            
    def critical(self, message: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Log critical message"""
        with self.lock:
            self.stats['total_logs'] += 1
            self.stats['error_count'] += 1  # Count as error
            self.main_logger.critical(message, extra=extra or {}, exc_info=exc_info)
            
    def log_request(self, method: str, url: str, status_code: int, 
                   response_time: float, proxy: Optional[str] = None):
        """Log HTTP request details"""
        extra = {
            'event_type': 'http_request',
            'method': method,
            'url': url,
            'status_code': status_code,
            'response_time': response_time,
            'proxy': proxy
        }
        
        if status_code >= 400:
            self.warning(f"{method} {url} -> {status_code} ({response_time:.3f}s)", extra=extra)
        else:
            self.info(f"{method} {url} -> {status_code} ({response_time:.3f}s)", extra=extra)
            
    def log_config_execution(self, config_name: str, entry: str, 
                           result: str, execution_time: float):
        """Log config execution result"""
        extra = {
            'event_type': 'config_execution',
            'config_name': config_name,
            'entry': entry,
            'result': result,
            'execution_time': execution_time
        }
        
        if result == 'hit':
            self.info(f"✅ HIT: {config_name} - {entry} ({execution_time:.3f}s)", extra=extra)
        elif result == 'fail':
            self.debug(f"❌ FAIL: {config_name} - {entry} ({execution_time:.3f}s)", extra=extra)
        elif result == 'error':
            self.error(f"⚠️ ERROR: {config_name} - {entry} ({execution_time:.3f}s)", extra=extra)
        elif result == 'ban':
            self.warning(f"🚫 BAN: {config_name} - {entry} ({execution_time:.3f}s)", extra=extra)
            
    def log_proxy_status(self, proxy: str, status: str, response_time: Optional[float] = None):
        """Log proxy status change"""
        extra = {
            'event_type': 'proxy_status',
            'proxy': proxy,
            'status': status,
            'response_time': response_time
        }
        
        if status == 'working':
            self.info(f"🔗 Proxy {proxy} is working ({response_time:.3f}s)", extra=extra)
        elif status == 'dead':
            self.warning(f"💀 Proxy {proxy} is dead", extra=extra)
        elif status == 'banned':
            self.warning(f"🚫 Proxy {proxy} is banned", extra=extra)
            
    def log_captcha_result(self, captcha_type: str, service: str, 
                          success: bool, solve_time: float):
        """Log captcha solving result"""
        extra = {
            'event_type': 'captcha_solve',
            'captcha_type': captcha_type,
            'service': service,
            'success': success,
            'solve_time': solve_time
        }
        
        if success:
            self.info(f"🔓 Captcha solved: {captcha_type} via {service} ({solve_time:.1f}s)", extra=extra)
        else:
            self.warning(f"❌ Captcha failed: {captcha_type} via {service}", extra=extra)
            
    def log_wordlist_loaded(self, name: str, entries: int, load_time: float):
        """Log wordlist loading"""
        extra = {
            'event_type': 'wordlist_loaded',
            'name': name,
            'entries': entries,
            'load_time': load_time
        }
        
        self.info(f"📝 Loaded wordlist '{name}': {entries} entries ({load_time:.3f}s)", extra=extra)
        
    def add_filter(self, name: str, filter_func):
        """Add custom log filter"""
        self.filters[name] = filter_func
        
        # Apply filter to all handlers
        for handler in self.main_logger.handlers:
            handler.addFilter(filter_func)
            
    def remove_filter(self, name: str):
        """Remove custom log filter"""
        if name in self.filters:
            filter_func = self.filters[name]
            
            # Remove from all handlers
            for handler in self.main_logger.handlers:
                handler.removeFilter(filter_func)
                
            del self.filters[name]
            
    def set_level(self, level: LogLevel):
        """Change logging level"""
        self.level = level
        self.main_logger.setLevel(level.value)
        
        # Update console handler level
        for handler in self.main_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(level.value)
                
    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics"""
        return self.stats.copy()
        
    def export_logs(self, output_path: str, 
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   level_filter: Optional[LogLevel] = None):
        """Export logs to file with optional filtering"""
        main_log_file = self.log_dir / f"{self.name.lower()}.log"
        
        if not main_log_file.exists():
            return False
            
        try:
            with open(main_log_file, 'r', encoding='utf-8') as infile:
                with open(output_path, 'w', encoding='utf-8') as outfile:
                    for line in infile:
                        # Apply filters if specified
                        if self._should_include_line(line, start_date, end_date, level_filter):
                            outfile.write(line)
                            
            self.info(f"Exported logs to {output_path}")
            return True
            
        except Exception as e:
            self.error(f"Failed to export logs: {e}")
            return False
            
    def _should_include_line(self, line: str, 
                           start_date: Optional[datetime],
                           end_date: Optional[datetime],
                           level_filter: Optional[LogLevel]) -> bool:
        """Check if log line should be included in export"""
        # Basic implementation - could be enhanced
        if level_filter:
            if level_filter.name not in line:
                return False
                
        # Date filtering would require parsing the timestamp
        # This is a simplified version
        return True
        
    def clear_logs(self):
        """Clear all log files"""
        try:
            for log_file in self.log_dir.glob(f"{self.name.lower()}*.log*"):
                log_file.unlink()
                
            for log_file in self.log_dir.glob(f"{self.name.lower()}*.json*"):
                log_file.unlink()
                
            self.info("Cleared all log files")
            
            # Reset statistics
            self.stats = {
                'total_logs': 0,
                'error_count': 0,
                'warning_count': 0,
                'info_count': 0,
                'debug_count': 0
            }
            
        except Exception as e:
            self.error(f"Failed to clear logs: {e}")
            
    def create_session_logger(self, session_id: str) -> 'SessionLogger':
        """Create a session-specific logger"""
        return SessionLogger(self, session_id)

class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                              'pathname', 'filename', 'module', 'lineno', 
                              'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process',
                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    log_data[key] = value
                    
        return json.dumps(log_data)

class SessionLogger:
    """Session-specific logger that wraps main logger"""
    
    def __init__(self, main_logger: Logger, session_id: str):
        self.main_logger = main_logger
        self.session_id = session_id
        
    def _add_session_info(self, extra: Optional[Dict] = None) -> Dict:
        """Add session information to extra data"""
        session_extra = {'session_id': self.session_id}
        if extra:
            session_extra.update(extra)
        return session_extra
        
    def debug(self, message: str, extra: Optional[Dict] = None):
        self.main_logger.debug(f"[{self.session_id}] {message}", 
                              extra=self._add_session_info(extra))
        
    def info(self, message: str, extra: Optional[Dict] = None):
        self.main_logger.info(f"[{self.session_id}] {message}", 
                             extra=self._add_session_info(extra))
        
    def warning(self, message: str, extra: Optional[Dict] = None):
        self.main_logger.warning(f"[{self.session_id}] {message}", 
                                extra=self._add_session_info(extra))
        
    def error(self, message: str, extra: Optional[Dict] = None, exc_info: bool = False):
        self.main_logger.error(f"[{self.session_id}] {message}", 
                              extra=self._add_session_info(extra), exc_info=exc_info)
        
    def critical(self, message: str, extra: Optional[Dict] = None, exc_info: bool = False):
        self.main_logger.critical(f"[{self.session_id}] {message}", 
                                 extra=self._add_session_info(extra), exc_info=exc_info)

# Global logger instance
_global_logger = None

def get_logger(name: str = "OpenBullet") -> Logger:
    """Get global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger(name)
    return _global_logger

def setup_logging(log_dir: str = "logs", 
                 level: LogLevel = LogLevel.INFO,
                 format_type: LogFormat = LogFormat.DETAILED):
    """Setup global logging configuration"""
    global _global_logger
    _global_logger = Logger(
        name="OpenBullet",
        log_dir=log_dir,
        level=level,
        format_type=format_type
    )
    return _global_logger