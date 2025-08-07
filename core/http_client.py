"""
Advanced HTTP Client for OpenBullet Python
Supports all HTTP methods, proxies (HTTP/SOCKS), cookies, custom headers,
SSL verification control, and comprehensive error handling.
"""

import aiohttp
import asyncio
import ssl
import random
import time
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Union, Tuple, Any
import json
import re
from dataclasses import dataclass
from enum import Enum

class ProxyType(Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"

@dataclass
class ProxyConfig:
    """Proxy configuration class"""
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    
    def to_url(self) -> str:
        """Convert proxy config to URL format"""
        auth = f"{self.username}:{self.password}@" if self.username and self.password else ""
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

@dataclass 
class HttpResponse:
    """HTTP Response wrapper with additional metadata"""
    status_code: int
    headers: Dict[str, str]
    text: str
    content: bytes
    url: str
    cookies: Dict[str, str]
    elapsed: float
    proxy_used: Optional[str] = None
    
    @property
    def json_data(self) -> Optional[Dict]:
        """Parse response as JSON"""
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, TypeError):
            return None
            
    def has_text(self, text: str, case_sensitive: bool = True) -> bool:
        """Check if response contains specific text"""
        search_text = self.text if case_sensitive else self.text.lower()
        target_text = text if case_sensitive else text.lower()
        return target_text in search_text
        
    def regex_search(self, pattern: str, flags: int = 0) -> Optional[re.Match]:
        """Search for regex pattern in response"""
        return re.search(pattern, self.text, flags)
        
    def extract_between(self, start: str, end: str) -> List[str]:
        """Extract text between two delimiters"""
        results = []
        pattern = re.escape(start) + "(.*?)" + re.escape(end)
        matches = re.findall(pattern, self.text, re.DOTALL)
        return matches

class HttpClient:
    """
    Advanced HTTP Client with proxy rotation, cookie management,
    and comprehensive request handling capabilities
    """
    
    def __init__(self, 
                 timeout: int = 30,
                 max_retries: int = 3,
                 follow_redirects: bool = True,
                 verify_ssl: bool = False,
                 max_redirects: int = 10):
        
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.follow_redirects = follow_redirects
        self.verify_ssl = verify_ssl
        self.max_redirects = max_redirects
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookies = aiohttp.CookieJar()
        
        # Default headers
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Statistics
        self.stats = {
            'requests_sent': 0,
            'requests_failed': 0,
            'total_bytes': 0,
            'avg_response_time': 0
        }
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()
        
    async def create_session(self, proxy: Optional[ProxyConfig] = None):
        """Create aiohttp session with optional proxy"""
        connector_kwargs = {
            'ssl': ssl.create_default_context() if self.verify_ssl else False,
            'limit': 100,
            'limit_per_host': 20,
            'ttl_dns_cache': 300
        }
        
        # Configure proxy if provided
        if proxy:
            if proxy.proxy_type in [ProxyType.HTTP, ProxyType.HTTPS]:
                connector_kwargs['trust_env'] = True
            # For SOCKS proxies, we'd need aiohttp-socks
            
        connector = aiohttp.TCPConnector(**connector_kwargs)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            cookie_jar=self.cookies,
            headers=self.default_headers
        )
        
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
            
    def set_cookies(self, cookies: Dict[str, str], domain: str = ""):
        """Set cookies for requests"""
        for name, value in cookies.items():
            self.cookies.update_cookies({name: value}, response_url=domain or "http://example.com")
            
    def clear_cookies(self):
        """Clear all cookies"""
        self.cookies.clear()
        
    def get_cookies(self) -> Dict[str, str]:
        """Get current cookies as dictionary"""
        cookies = {}
        for cookie in self.cookies:
            cookies[cookie.key] = cookie.value
        return cookies
        
    async def request(self,
                     method: str,
                     url: str,
                     headers: Optional[Dict[str, str]] = None,
                     data: Optional[Union[str, bytes, Dict]] = None,
                     json_data: Optional[Dict] = None,
                     params: Optional[Dict] = None,
                     proxy: Optional[ProxyConfig] = None,
                     allow_redirects: Optional[bool] = None,
                     auth: Optional[Tuple[str, str]] = None) -> HttpResponse:
        """
        Make HTTP request with comprehensive options
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Target URL
            headers: Custom headers
            data: Request body data
            json_data: JSON data (will be serialized)
            params: URL parameters
            proxy: Proxy configuration
            allow_redirects: Override default redirect behavior
            auth: Basic authentication (username, password)
            
        Returns:
            HttpResponse object with response data and metadata
        """
        
        if not self.session:
            await self.create_session(proxy)
            
        # Merge headers
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
            
        # Handle authentication
        auth_header = None
        if auth:
            import base64
            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            auth_header = aiohttp.BasicAuth(auth[0], auth[1])
            
        # Prepare request data
        request_kwargs = {
            'method': method.upper(),
            'url': url,
            'headers': request_headers,
            'params': params,
            'allow_redirects': allow_redirects if allow_redirects is not None else self.follow_redirects,
            'max_redirects': self.max_redirects,
            'auth': auth_header
        }
        
        # Handle request body
        if json_data:
            request_kwargs['json'] = json_data
        elif data:
            if isinstance(data, dict):
                request_kwargs['data'] = aiohttp.FormData(data)
            else:
                request_kwargs['data'] = data
                
        # Configure proxy for this request
        if proxy:
            if proxy.proxy_type in [ProxyType.HTTP, ProxyType.HTTPS]:
                request_kwargs['proxy'] = proxy.to_url()
                if proxy.username and proxy.password:
                    request_kwargs['proxy_auth'] = aiohttp.BasicAuth(proxy.username, proxy.password)
                    
        # Execute request with retries
        last_exception = None
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session.request(**request_kwargs) as response:
                    # Read response
                    content = await response.read()
                    text = content.decode('utf-8', errors='ignore')
                    
                    # Calculate elapsed time
                    elapsed = time.time() - start_time
                    
                    # Extract cookies
                    response_cookies = {}
                    for cookie in response.cookies:
                        response_cookies[cookie.key] = cookie.value
                        
                    # Update statistics
                    self.stats['requests_sent'] += 1
                    self.stats['total_bytes'] += len(content)
                    
                    # Create response object
                    http_response = HttpResponse(
                        status_code=response.status,
                        headers=dict(response.headers),
                        text=text,
                        content=content,
                        url=str(response.url),
                        cookies=response_cookies,
                        elapsed=elapsed,
                        proxy_used=proxy.to_url() if proxy else None
                    )
                    
                    return http_response
                    
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    self.stats['requests_failed'] += 1
                    raise e
                    
    async def get(self, url: str, **kwargs) -> HttpResponse:
        """HTTP GET request"""
        return await self.request('GET', url, **kwargs)
        
    async def post(self, url: str, **kwargs) -> HttpResponse:
        """HTTP POST request"""
        return await self.request('POST', url, **kwargs)
        
    async def put(self, url: str, **kwargs) -> HttpResponse:
        """HTTP PUT request"""
        return await self.request('PUT', url, **kwargs)
        
    async def delete(self, url: str, **kwargs) -> HttpResponse:
        """HTTP DELETE request"""
        return await self.request('DELETE', url, **kwargs)
        
    async def head(self, url: str, **kwargs) -> HttpResponse:
        """HTTP HEAD request"""
        return await self.request('HEAD', url, **kwargs)
        
    async def options(self, url: str, **kwargs) -> HttpResponse:
        """HTTP OPTIONS request"""
        return await self.request('OPTIONS', url, **kwargs)
        
    def set_default_headers(self, headers: Dict[str, str]):
        """Update default headers"""
        self.default_headers.update(headers)
        
    def set_user_agent(self, user_agent: str):
        """Set User-Agent header"""
        self.default_headers['User-Agent'] = user_agent
        
    def get_random_user_agent(self) -> str:
        """Get random User-Agent string"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        return random.choice(user_agents)
        
    def randomize_user_agent(self):
        """Set random User-Agent"""
        self.set_user_agent(self.get_random_user_agent())
        
    async def test_proxy(self, proxy: ProxyConfig, test_url: str = "http://httpbin.org/ip") -> bool:
        """Test if proxy is working"""
        try:
            response = await self.get(test_url, proxy=proxy)
            return response.status_code == 200
        except Exception:
            return False
            
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        if self.stats['requests_sent'] > 0:
            self.stats['avg_response_time'] = self.stats['total_bytes'] / self.stats['requests_sent']
        return self.stats.copy()
        
    async def batch_requests(self, 
                           requests: List[Dict], 
                           max_concurrent: int = 10) -> List[HttpResponse]:
        """
        Execute multiple requests concurrently
        
        Args:
            requests: List of request dictionaries with 'method', 'url', and other params
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of HttpResponse objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_request(req_config):
            async with semaphore:
                return await self.request(**req_config)
                
        tasks = [bounded_request(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

# Example usage and utility functions
async def create_http_client(**kwargs) -> HttpClient:
    """Factory function to create HTTP client"""
    client = HttpClient(**kwargs)
    await client.create_session()
    return client

def parse_proxy_string(proxy_string: str) -> ProxyConfig:
    """
    Parse proxy string in various formats:
    - host:port
    - type://host:port
    - type://username:password@host:port
    """
    try:
        if '://' in proxy_string:
            # Full URL format
            parsed = urlparse(proxy_string)
            return ProxyConfig(
                host=parsed.hostname,
                port=parsed.port,
                proxy_type=ProxyType(parsed.scheme),
                username=parsed.username,
                password=parsed.password
            )
        else:
            # Simple host:port format
            host, port = proxy_string.split(':')
            return ProxyConfig(host=host, port=int(port))
    except Exception as e:
        raise ValueError(f"Invalid proxy format: {proxy_string}") from e