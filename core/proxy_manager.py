"""
Advanced Proxy Manager for OpenBullet Python
Handles proxy rotation, validation, statistics, and multi-protocol support
"""

import asyncio
import random
import time
import aiohttp
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import re
from urllib.parse import urlparse
import logging

from .http_client import ProxyConfig, ProxyType

class ProxyStatus(Enum):
    UNKNOWN = "unknown"
    WORKING = "working" 
    DEAD = "dead"
    TIMEOUT = "timeout"
    BANNED = "banned"
    CHECKING = "checking"

@dataclass
class ProxyStats:
    """Statistics for a proxy"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_used: Optional[float] = None
    last_checked: Optional[float] = None
    status: ProxyStatus = ProxyStatus.UNKNOWN
    ban_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
        
    @property
    def is_healthy(self) -> bool:
        """Check if proxy is considered healthy"""
        return (self.status == ProxyStatus.WORKING and 
                self.success_rate >= 50 and 
                self.ban_count < 3)

@dataclass
class ManagedProxy:
    """Proxy with management metadata"""
    config: ProxyConfig
    stats: ProxyStats = field(default_factory=ProxyStats)
    source: str = "manual"
    tags: Set[str] = field(default_factory=set)
    
    def __hash__(self):
        return hash(f"{self.config.host}:{self.config.port}")
        
    def __eq__(self, other):
        if not isinstance(other, ManagedProxy):
            return False
        return (self.config.host == other.config.host and 
                self.config.port == other.config.port)

class ProxyRotationStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    BEST_PERFORMANCE = "best_performance"
    LEAST_USED = "least_used"

class ProxyManager:
    """
    Advanced proxy management system with rotation, validation,
    and comprehensive statistics tracking
    """
    
    def __init__(self, 
                 rotation_strategy: ProxyRotationStrategy = ProxyRotationStrategy.ROUND_ROBIN,
                 max_retries: int = 3,
                 check_interval: int = 300,
                 auto_remove_dead: bool = True):
        
        self.proxies: List[ManagedProxy] = []
        self.rotation_strategy = rotation_strategy
        self.max_retries = max_retries
        self.check_interval = check_interval
        self.auto_remove_dead = auto_remove_dead
        
        # Rotation state
        self.current_index = 0
        self.usage_count: Dict[str, int] = {}
        
        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        
        # Background tasks
        self.check_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Logger
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def add_proxy(self, proxy: ProxyConfig, source: str = "manual", tags: Set[str] = None) -> bool:
        """
        Add a proxy to the manager
        
        Args:
            proxy: ProxyConfig object
            source: Source identifier for the proxy
            tags: Optional tags for categorization
            
        Returns:
            True if proxy was added, False if already exists
        """
        managed_proxy = ManagedProxy(
            config=proxy,
            source=source,
            tags=tags or set()
        )
        
        if managed_proxy not in self.proxies:
            self.proxies.append(managed_proxy)
            self.logger.info(f"Added proxy {proxy.host}:{proxy.port} from {source}")
            return True
        return False
        
    def remove_proxy(self, host: str, port: int) -> bool:
        """Remove proxy by host and port"""
        for i, proxy in enumerate(self.proxies):
            if proxy.config.host == host and proxy.config.port == port:
                del self.proxies[i]
                self.logger.info(f"Removed proxy {host}:{port}")
                return True
        return False
        
    def load_proxies(self, file_path: str, source: str = None) -> int:
        """
        Load proxies from file
        
        Supports formats:
        - host:port
        - protocol://host:port
        - protocol://username:password@host:port
        - JSON format with metadata
        
        Returns:
            Number of proxies loaded
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Proxy file not found: {file_path}")
            
        source = source or path.name
        loaded_count = 0
        
        try:
            content = path.read_text(encoding='utf-8')
            
            # Try JSON format first
            if content.strip().startswith('[') or content.strip().startswith('{'):
                loaded_count = self._load_json_proxies(content, source)
            else:
                loaded_count = self._load_text_proxies(content, source)
                
        except Exception as e:
            self.logger.error(f"Error loading proxies from {file_path}: {e}")
            raise
            
        self.logger.info(f"Loaded {loaded_count} proxies from {file_path}")
        return loaded_count
        
    def _load_json_proxies(self, content: str, source: str) -> int:
        """Load proxies from JSON format"""
        data = json.loads(content)
        loaded_count = 0
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    proxy_config = self._parse_proxy_dict(item)
                    if proxy_config:
                        tags = set(item.get('tags', []))
                        self.add_proxy(proxy_config, source, tags)
                        loaded_count += 1
                else:
                    proxy_config = self._parse_proxy_string(str(item))
                    if proxy_config:
                        self.add_proxy(proxy_config, source)
                        loaded_count += 1
                        
        return loaded_count
        
    def _load_text_proxies(self, content: str, source: str) -> int:
        """Load proxies from text format (one per line)"""
        loaded_count = 0
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                proxy_config = self._parse_proxy_string(line)
                if proxy_config:
                    self.add_proxy(proxy_config, source)
                    loaded_count += 1
                    
        return loaded_count
        
    def _parse_proxy_dict(self, data: Dict) -> Optional[ProxyConfig]:
        """Parse proxy from dictionary format"""
        try:
            return ProxyConfig(
                host=data['host'],
                port=int(data['port']),
                proxy_type=ProxyType(data.get('type', 'http')),
                username=data.get('username'),
                password=data.get('password')
            )
        except (KeyError, ValueError, TypeError):
            return None
            
    def _parse_proxy_string(self, proxy_str: str) -> Optional[ProxyConfig]:
        """Parse proxy from string format"""
        try:
            # Handle URL format
            if '://' in proxy_str:
                parsed = urlparse(proxy_str)
                return ProxyConfig(
                    host=parsed.hostname,
                    port=parsed.port,
                    proxy_type=ProxyType(parsed.scheme),
                    username=parsed.username,
                    password=parsed.password
                )
            else:
                # Simple host:port format
                if ':' in proxy_str:
                    host, port = proxy_str.rsplit(':', 1)
                    return ProxyConfig(host=host, port=int(port))
                    
        except (ValueError, TypeError, AttributeError):
            self.logger.warning(f"Failed to parse proxy: {proxy_str}")
            
        return None
        
    def get_proxy(self, exclude_dead: bool = True, tags: Set[str] = None) -> Optional[ProxyConfig]:
        """
        Get next proxy based on rotation strategy
        
        Args:
            exclude_dead: Skip dead proxies
            tags: Filter by tags (proxy must have at least one matching tag)
            
        Returns:
            ProxyConfig or None if no suitable proxy found
        """
        available_proxies = self._get_available_proxies(exclude_dead, tags)
        
        if not available_proxies:
            return None
            
        if self.rotation_strategy == ProxyRotationStrategy.ROUND_ROBIN:
            proxy = self._get_round_robin(available_proxies)
        elif self.rotation_strategy == ProxyRotationStrategy.RANDOM:
            proxy = random.choice(available_proxies)
        elif self.rotation_strategy == ProxyRotationStrategy.BEST_PERFORMANCE:
            proxy = self._get_best_performance(available_proxies)
        elif self.rotation_strategy == ProxyRotationStrategy.LEAST_USED:
            proxy = self._get_least_used(available_proxies)
        else:
            proxy = available_proxies[0]
            
        # Update usage stats
        proxy_key = f"{proxy.config.host}:{proxy.config.port}"
        self.usage_count[proxy_key] = self.usage_count.get(proxy_key, 0) + 1
        proxy.stats.last_used = time.time()
        
        return proxy.config
        
    def _get_available_proxies(self, exclude_dead: bool, tags: Set[str]) -> List[ManagedProxy]:
        """Get list of available proxies based on filters"""
        available = []
        
        for proxy in self.proxies:
            # Filter by status
            if exclude_dead and proxy.stats.status == ProxyStatus.DEAD:
                continue
                
            # Filter by tags
            if tags and not (tags & proxy.tags):
                continue
                
            available.append(proxy)
            
        return available
        
    def _get_round_robin(self, proxies: List[ManagedProxy]) -> ManagedProxy:
        """Get proxy using round-robin strategy"""
        if self.current_index >= len(proxies):
            self.current_index = 0
            
        proxy = proxies[self.current_index]
        self.current_index += 1
        return proxy
        
    def _get_best_performance(self, proxies: List[ManagedProxy]) -> ManagedProxy:
        """Get proxy with best performance"""
        return max(proxies, key=lambda p: p.stats.success_rate)
        
    def _get_least_used(self, proxies: List[ManagedProxy]) -> ManagedProxy:
        """Get least used proxy"""
        return min(proxies, key=lambda p: self.usage_count.get(f"{p.config.host}:{p.config.port}", 0))
        
    async def check_proxy(self, proxy: ManagedProxy, 
                         test_url: str = "http://httpbin.org/ip", 
                         timeout: int = 10) -> ProxyStatus:
        """
        Check if a proxy is working
        
        Args:
            proxy: ManagedProxy to check
            test_url: URL to test against
            timeout: Request timeout
            
        Returns:
            ProxyStatus indicating the result
        """
        proxy.stats.status = ProxyStatus.CHECKING
        proxy.stats.last_checked = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                proxy_url = proxy.config.to_url()
                
                start_time = time.time()
                async with session.get(test_url, proxy=proxy_url) as response:
                    elapsed = time.time() - start_time
                    
                    if response.status == 200:
                        proxy.stats.status = ProxyStatus.WORKING
                        proxy.stats.avg_response_time = elapsed
                        proxy.stats.successful_requests += 1
                        self.logger.debug(f"Proxy {proxy.config.host}:{proxy.config.port} is working")
                    else:
                        proxy.stats.status = ProxyStatus.DEAD
                        proxy.stats.failed_requests += 1
                        
        except asyncio.TimeoutError:
            proxy.stats.status = ProxyStatus.TIMEOUT
            proxy.stats.failed_requests += 1
            self.logger.debug(f"Proxy {proxy.config.host}:{proxy.config.port} timed out")
            
        except Exception as e:
            proxy.stats.status = ProxyStatus.DEAD
            proxy.stats.failed_requests += 1
            self.logger.debug(f"Proxy {proxy.config.host}:{proxy.config.port} failed: {e}")
            
        proxy.stats.total_requests += 1
        return proxy.stats.status
        
    async def check_all_proxies(self, max_concurrent: int = 50) -> Dict[ProxyStatus, int]:
        """
        Check all proxies concurrently
        
        Args:
            max_concurrent: Maximum concurrent checks
            
        Returns:
            Dictionary with status counts
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_check(proxy):
            async with semaphore:
                return await self.check_proxy(proxy)
                
        tasks = [bounded_check(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        status_counts = {status: 0 for status in ProxyStatus}
        for result in results:
            if isinstance(result, ProxyStatus):
                status_counts[result] += 1
                
        # Remove dead proxies if configured
        if self.auto_remove_dead:
            dead_proxies = [p for p in self.proxies if p.stats.status == ProxyStatus.DEAD]
            for proxy in dead_proxies:
                self.remove_proxy(proxy.config.host, proxy.config.port)
                
        self.logger.info(f"Proxy check complete: {dict(status_counts)}")
        return status_counts
        
    def mark_proxy_banned(self, host: str, port: int):
        """Mark a proxy as banned"""
        for proxy in self.proxies:
            if proxy.config.host == host and proxy.config.port == port:
                proxy.stats.status = ProxyStatus.BANNED
                proxy.stats.ban_count += 1
                self.logger.warning(f"Marked proxy {host}:{port} as banned (count: {proxy.stats.ban_count})")
                break
                
    def mark_proxy_failed(self, host: str, port: int):
        """Mark a proxy request as failed"""
        for proxy in self.proxies:
            if proxy.config.host == host and proxy.config.port == port:
                proxy.stats.failed_requests += 1
                proxy.stats.total_requests += 1
                
                # Auto-mark as dead if too many failures
                if proxy.stats.success_rate < 20 and proxy.stats.total_requests > 10:
                    proxy.stats.status = ProxyStatus.DEAD
                    
                break
                
    def mark_proxy_success(self, host: str, port: int, response_time: float = 0):
        """Mark a proxy request as successful"""
        for proxy in self.proxies:
            if proxy.config.host == host and proxy.config.port == port:
                proxy.stats.successful_requests += 1
                proxy.stats.total_requests += 1
                
                if response_time > 0:
                    # Update average response time
                    current_avg = proxy.stats.avg_response_time
                    total_successful = proxy.stats.successful_requests
                    proxy.stats.avg_response_time = ((current_avg * (total_successful - 1)) + response_time) / total_successful
                    
                # Mark as working if it was unknown
                if proxy.stats.status == ProxyStatus.UNKNOWN:
                    proxy.stats.status = ProxyStatus.WORKING
                    
                break
                
    def get_statistics(self) -> Dict:
        """Get comprehensive proxy statistics"""
        total_proxies = len(self.proxies)
        working_proxies = len([p for p in self.proxies if p.stats.status == ProxyStatus.WORKING])
        dead_proxies = len([p for p in self.proxies if p.stats.status == ProxyStatus.DEAD])
        banned_proxies = len([p for p in self.proxies if p.stats.status == ProxyStatus.BANNED])
        
        return {
            'total_proxies': total_proxies,
            'working_proxies': working_proxies,
            'dead_proxies': dead_proxies,
            'banned_proxies': banned_proxies,
            'healthy_proxies': len([p for p in self.proxies if p.stats.is_healthy]),
            'avg_success_rate': sum(p.stats.success_rate for p in self.proxies) / total_proxies if total_proxies > 0 else 0,
            'total_requests': sum(p.stats.total_requests for p in self.proxies),
            'sources': list(set(p.source for p in self.proxies)),
            'proxy_types': list(set(p.config.proxy_type.value for p in self.proxies))
        }
        
    def get_active_proxies(self) -> List[str]:
        """Get list of active proxy strings"""
        return [f"{p.config.host}:{p.config.port}" for p in self.proxies 
                if p.stats.status in [ProxyStatus.WORKING, ProxyStatus.UNKNOWN]]
                
    def export_proxies(self, file_path: str, include_stats: bool = False, 
                      format_type: str = "text") -> bool:
        """
        Export proxies to file
        
        Args:
            file_path: Output file path
            include_stats: Include statistics in export
            format_type: "text" or "json"
            
        Returns:
            True if export successful
        """
        try:
            path = Path(file_path)
            
            if format_type == "json":
                data = []
                for proxy in self.proxies:
                    proxy_data = {
                        'host': proxy.config.host,
                        'port': proxy.config.port,
                        'type': proxy.config.proxy_type.value,
                        'username': proxy.config.username,
                        'password': proxy.config.password,
                        'source': proxy.source,
                        'tags': list(proxy.tags)
                    }
                    
                    if include_stats:
                        proxy_data['stats'] = {
                            'status': proxy.stats.status.value,
                            'total_requests': proxy.stats.total_requests,
                            'success_rate': proxy.stats.success_rate,
                            'avg_response_time': proxy.stats.avg_response_time,
                            'ban_count': proxy.stats.ban_count
                        }
                        
                    data.append(proxy_data)
                    
                path.write_text(json.dumps(data, indent=2), encoding='utf-8')
                
            else:  # text format
                lines = []
                for proxy in self.proxies:
                    if proxy.config.username and proxy.config.password:
                        line = f"{proxy.config.proxy_type.value}://{proxy.config.username}:{proxy.config.password}@{proxy.config.host}:{proxy.config.port}"
                    else:
                        line = f"{proxy.config.proxy_type.value}://{proxy.config.host}:{proxy.config.port}"
                        
                    if include_stats:
                        line += f" # {proxy.stats.status.value} ({proxy.stats.success_rate:.1f}%)"
                        
                    lines.append(line)
                    
                path.write_text('\n'.join(lines), encoding='utf-8')
                
            self.logger.info(f"Exported {len(self.proxies)} proxies to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export proxies: {e}")
            return False
            
    async def start_background_checker(self):
        """Start background proxy checking task"""
        if self.is_running:
            return
            
        self.is_running = True
        self.check_task = asyncio.create_task(self._background_checker())
        self.logger.info("Started background proxy checker")
        
    async def stop_background_checker(self):
        """Stop background proxy checking task"""
        self.is_running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
            self.check_task = None
            
        self.logger.info("Stopped background proxy checker")
        
    async def _background_checker(self):
        """Background task to periodically check proxies"""
        while self.is_running:
            try:
                await self.check_all_proxies()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Background checker error: {e}")
                await asyncio.sleep(60)  # Wait before retrying
                
    def filter_proxies(self, **filters) -> List[ManagedProxy]:
        """
        Filter proxies by various criteria
        
        Supported filters:
        - status: ProxyStatus
        - min_success_rate: float
        - max_response_time: float
        - source: str
        - tags: Set[str]
        - proxy_type: ProxyType
        """
        filtered = self.proxies.copy()
        
        if 'status' in filters:
            filtered = [p for p in filtered if p.stats.status == filters['status']]
            
        if 'min_success_rate' in filters:
            filtered = [p for p in filtered if p.stats.success_rate >= filters['min_success_rate']]
            
        if 'max_response_time' in filters:
            filtered = [p for p in filtered if p.stats.avg_response_time <= filters['max_response_time']]
            
        if 'source' in filters:
            filtered = [p for p in filtered if p.source == filters['source']]
            
        if 'tags' in filters:
            required_tags = filters['tags']
            filtered = [p for p in filtered if required_tags & p.tags]
            
        if 'proxy_type' in filters:
            filtered = [p for p in filtered if p.config.proxy_type == filters['proxy_type']]
            
        return filtered