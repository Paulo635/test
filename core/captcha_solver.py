"""
Captcha Solver for OpenBullet Python
Integrates with multiple captcha solving services and provides caching
"""

import asyncio
import aiohttp
import base64
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import json
import logging

class CaptchaType(Enum):
    IMAGE = "image"
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    FUNCAPTCHA = "funcaptcha"
    GEETEST = "geetest"
    TEXT = "text"

class CaptchaService(Enum):
    TWOCAPTCHA = "2captcha"
    ANTICAPTCHA = "anticaptcha"
    DEATHBYCAPTCHA = "deathbycaptcha"
    IMAGETYPERZ = "imagetyperz"
    CAPMONSTER = "capmonster"

@dataclass
class CaptchaTask:
    """Represents a captcha solving task"""
    task_id: str
    service: CaptchaService
    captcha_type: CaptchaType
    data: Dict[str, Any]
    submitted_at: float
    attempts: int = 0
    max_attempts: int = 3

@dataclass
class CaptchaResult:
    """Result of captcha solving"""
    success: bool
    solution: str = ""
    task_id: str = ""
    cost: float = 0.0
    solve_time: float = 0.0
    error_message: str = ""

class CaptchaSolver:
    """
    Advanced captcha solving system with multi-service support,
    caching, and automatic fallback
    """
    
    def __init__(self, 
                 cache_enabled: bool = True,
                 cache_duration: int = 3600,
                 max_concurrent_tasks: int = 10):
        
        self.cache_enabled = cache_enabled
        self.cache_duration = cache_duration
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # Service configurations
        self.service_configs = {}
        self.service_priorities = [
            CaptchaService.TWOCAPTCHA,
            CaptchaService.ANTICAPTCHA,
            CaptchaService.CAPMONSTER
        ]
        
        # Active tasks and cache
        self.active_tasks: Dict[str, CaptchaTask] = {}
        self.solution_cache: Dict[str, Dict] = {}
        
        # Statistics
        self.stats = {
            'total_solved': 0,
            'cache_hits': 0,
            'service_usage': {},
            'avg_solve_time': 0.0,
            'success_rate': 0.0
        }
        
        # Rate limiting
        self.rate_limits = {}
        self.last_requests = {}
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def configure_service(self, 
                         service: CaptchaService, 
                         api_key: str,
                         custom_config: Optional[Dict] = None):
        """Configure a captcha solving service"""
        config = {
            'api_key': api_key,
            'enabled': True,
            'priority': 1,
            'timeout': 120,
            'max_retries': 3
        }
        
        if custom_config:
            config.update(custom_config)
            
        # Service-specific configurations
        if service == CaptchaService.TWOCAPTCHA:
            config.update({
                'submit_url': 'http://2captcha.com/in.php',
                'result_url': 'http://2captcha.com/res.php',
                'balance_url': 'http://2captcha.com/res.php?key={}&action=getbalance'
            })
        elif service == CaptchaService.ANTICAPTCHA:
            config.update({
                'base_url': 'https://api.anti-captcha.com',
                'create_task_url': '/createTask',
                'get_result_url': '/getTaskResult',
                'balance_url': '/getBalance'
            })
        elif service == CaptchaService.CAPMONSTER:
            config.update({
                'base_url': 'https://api.capmonster.cloud',
                'create_task_url': '/createTask',
                'get_result_url': '/getTaskResult',
                'balance_url': '/getBalance'
            })
            
        self.service_configs[service] = config
        self.logger.info(f"Configured {service.value} captcha service")
        
    async def solve_captcha(self, 
                           captcha_type: CaptchaType,
                           captcha_data: Dict[str, Any],
                           preferred_service: Optional[CaptchaService] = None,
                           timeout: int = 120) -> CaptchaResult:
        """
        Solve a captcha using configured services
        
        Args:
            captcha_type: Type of captcha to solve
            captcha_data: Captcha data (image, sitekey, etc.)
            preferred_service: Preferred solving service
            timeout: Maximum time to wait for solution
            
        Returns:
            CaptchaResult with solution or error
        """
        # Check cache first
        if self.cache_enabled:
            cache_key = self._generate_cache_key(captcha_type, captcha_data)
            cached_result = self._get_cached_solution(cache_key)
            if cached_result:
                self.stats['cache_hits'] += 1
                return cached_result
                
        # Determine service order
        services = self._get_service_order(preferred_service)
        
        for service in services:
            if not self._is_service_available(service):
                continue
                
            try:
                result = await self._solve_with_service(
                    service, captcha_type, captcha_data, timeout
                )
                
                if result.success:
                    # Cache successful solution
                    if self.cache_enabled:
                        self._cache_solution(cache_key, result)
                        
                    # Update statistics
                    self._update_stats(service, result, True)
                    return result
                    
            except Exception as e:
                self.logger.warning(f"Service {service.value} failed: {e}")
                continue
                
        # All services failed
        result = CaptchaResult(
            success=False,
            error_message="All captcha services failed"
        )
        self._update_stats(None, result, False)
        return result
        
    async def _solve_with_service(self, 
                                 service: CaptchaService,
                                 captcha_type: CaptchaType,
                                 captcha_data: Dict[str, Any],
                                 timeout: int) -> CaptchaResult:
        """Solve captcha with specific service"""
        start_time = time.time()
        
        if service == CaptchaService.TWOCAPTCHA:
            return await self._solve_2captcha(captcha_type, captcha_data, timeout)
        elif service == CaptchaService.ANTICAPTCHA:
            return await self._solve_anticaptcha(captcha_type, captcha_data, timeout)
        elif service == CaptchaService.CAPMONSTER:
            return await self._solve_capmonster(captcha_type, captcha_data, timeout)
        else:
            raise ValueError(f"Unsupported service: {service}")
            
    async def _solve_2captcha(self, 
                             captcha_type: CaptchaType,
                             captcha_data: Dict[str, Any],
                             timeout: int) -> CaptchaResult:
        """Solve captcha using 2captcha service"""
        config = self.service_configs[CaptchaService.TWOCAPTCHA]
        
        async with aiohttp.ClientSession() as session:
            # Submit captcha
            submit_data = {
                'key': config['api_key'],
                'method': self._get_2captcha_method(captcha_type),
                'json': 1
            }
            
            # Add captcha-specific data
            if captcha_type == CaptchaType.IMAGE:
                if 'image_path' in captcha_data:
                    with open(captcha_data['image_path'], 'rb') as f:
                        image_data = base64.b64encode(f.read()).decode()
                        submit_data['body'] = image_data
                elif 'image_base64' in captcha_data:
                    submit_data['body'] = captcha_data['image_base64']
                    
            elif captcha_type == CaptchaType.RECAPTCHA_V2:
                submit_data.update({
                    'googlekey': captcha_data['sitekey'],
                    'pageurl': captcha_data['page_url']
                })
                
            elif captcha_type == CaptchaType.RECAPTCHA_V3:
                submit_data.update({
                    'googlekey': captcha_data['sitekey'],
                    'pageurl': captcha_data['page_url'],
                    'version': 'v3',
                    'action': captcha_data.get('action', 'verify'),
                    'min_score': captcha_data.get('min_score', 0.3)
                })
                
            # Submit task
            async with session.post(config['submit_url'], data=submit_data) as response:
                result = await response.json()
                
                if result.get('status') != 1:
                    return CaptchaResult(
                        success=False,
                        error_message=result.get('error_text', 'Unknown error')
                    )
                    
                task_id = result['request']
                
            # Wait for solution
            start_time = time.time()
            while time.time() - start_time < timeout:
                await asyncio.sleep(5)  # Wait before checking
                
                check_data = {
                    'key': config['api_key'],
                    'action': 'get',
                    'id': task_id,
                    'json': 1
                }
                
                async with session.get(config['result_url'], params=check_data) as response:
                    result = await response.json()
                    
                    if result.get('status') == 1:
                        # Solution ready
                        return CaptchaResult(
                            success=True,
                            solution=result['request'],
                            task_id=task_id,
                            solve_time=time.time() - start_time
                        )
                    elif result.get('error_text') and result['error_text'] != 'CAPCHA_NOT_READY':
                        return CaptchaResult(
                            success=False,
                            error_message=result['error_text']
                        )
                        
            return CaptchaResult(
                success=False,
                error_message="Timeout waiting for solution"
            )
            
    async def _solve_anticaptcha(self, 
                                captcha_type: CaptchaType,
                                captcha_data: Dict[str, Any],
                                timeout: int) -> CaptchaResult:
        """Solve captcha using AntiCaptcha service"""
        config = self.service_configs[CaptchaService.ANTICAPTCHA]
        base_url = config['base_url']
        
        async with aiohttp.ClientSession() as session:
            # Create task
            task_data = {
                'clientKey': config['api_key'],
                'task': self._build_anticaptcha_task(captcha_type, captcha_data)
            }
            
            async with session.post(f"{base_url}/createTask", json=task_data) as response:
                result = await response.json()
                
                if result.get('errorId') != 0:
                    return CaptchaResult(
                        success=False,
                        error_message=result.get('errorDescription', 'Unknown error')
                    )
                    
                task_id = result['taskId']
                
            # Wait for solution
            start_time = time.time()
            while time.time() - start_time < timeout:
                await asyncio.sleep(5)
                
                check_data = {
                    'clientKey': config['api_key'],
                    'taskId': task_id
                }
                
                async with session.post(f"{base_url}/getTaskResult", json=check_data) as response:
                    result = await response.json()
                    
                    if result.get('status') == 'ready':
                        solution = result['solution'].get('gRecaptchaResponse') or result['solution'].get('text', '')
                        return CaptchaResult(
                            success=True,
                            solution=solution,
                            task_id=str(task_id),
                            solve_time=time.time() - start_time
                        )
                    elif result.get('status') == 'processing':
                        continue
                    else:
                        return CaptchaResult(
                            success=False,
                            error_message=result.get('errorDescription', 'Unknown error')
                        )
                        
            return CaptchaResult(
                success=False,
                error_message="Timeout waiting for solution"
            )
            
    async def _solve_capmonster(self, 
                               captcha_type: CaptchaType,
                               captcha_data: Dict[str, Any],
                               timeout: int) -> CaptchaResult:
        """Solve captcha using CapMonster service"""
        # Similar implementation to AntiCaptcha (same API structure)
        config = self.service_configs[CaptchaService.CAPMONSTER]
        return await self._solve_anticaptcha(captcha_type, captcha_data, timeout)
        
    def _get_2captcha_method(self, captcha_type: CaptchaType) -> str:
        """Get 2captcha method for captcha type"""
        if captcha_type == CaptchaType.IMAGE:
            return 'base64'
        elif captcha_type == CaptchaType.RECAPTCHA_V2:
            return 'userrecaptcha'
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            return 'userrecaptcha'
        elif captcha_type == CaptchaType.HCAPTCHA:
            return 'hcaptcha'
        else:
            return 'base64'
            
    def _build_anticaptcha_task(self, 
                               captcha_type: CaptchaType,
                               captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build AntiCaptcha task object"""
        if captcha_type == CaptchaType.IMAGE:
            return {
                'type': 'ImageToTextTask',
                'body': captcha_data.get('image_base64', ''),
                'phrase': captcha_data.get('phrase', False),
                'case': captcha_data.get('case_sensitive', False),
                'numeric': captcha_data.get('numeric', 0),
                'math': captcha_data.get('math', False),
                'minLength': captcha_data.get('min_length', 0),
                'maxLength': captcha_data.get('max_length', 0)
            }
        elif captcha_type == CaptchaType.RECAPTCHA_V2:
            return {
                'type': 'NoCaptchaTaskProxyless',
                'websiteURL': captcha_data['page_url'],
                'websiteKey': captcha_data['sitekey']
            }
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            return {
                'type': 'RecaptchaV3TaskProxyless',
                'websiteURL': captcha_data['page_url'],
                'websiteKey': captcha_data['sitekey'],
                'minScore': captcha_data.get('min_score', 0.3),
                'pageAction': captcha_data.get('action', 'verify')
            }
        elif captcha_type == CaptchaType.HCAPTCHA:
            return {
                'type': 'HCaptchaTaskProxyless',
                'websiteURL': captcha_data['page_url'],
                'websiteKey': captcha_data['sitekey']
            }
        else:
            raise ValueError(f"Unsupported captcha type: {captcha_type}")
            
    def _generate_cache_key(self, 
                           captcha_type: CaptchaType,
                           captcha_data: Dict[str, Any]) -> str:
        """Generate cache key for captcha"""
        import hashlib
        
        # Create cache key based on captcha data
        cache_data = f"{captcha_type.value}:{json.dumps(captcha_data, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()
        
    def _get_cached_solution(self, cache_key: str) -> Optional[CaptchaResult]:
        """Get cached solution if valid"""
        if cache_key not in self.solution_cache:
            return None
            
        cached = self.solution_cache[cache_key]
        if time.time() - cached['timestamp'] > self.cache_duration:
            del self.solution_cache[cache_key]
            return None
            
        return CaptchaResult(
            success=True,
            solution=cached['solution'],
            task_id=cached.get('task_id', ''),
            solve_time=0.0  # Cached result
        )
        
    def _cache_solution(self, cache_key: str, result: CaptchaResult):
        """Cache a successful solution"""
        self.solution_cache[cache_key] = {
            'solution': result.solution,
            'task_id': result.task_id,
            'timestamp': time.time()
        }
        
        # Limit cache size
        if len(self.solution_cache) > 1000:
            # Remove oldest entries
            oldest_keys = sorted(
                self.solution_cache.keys(),
                key=lambda k: self.solution_cache[k]['timestamp']
            )[:100]
            
            for key in oldest_keys:
                del self.solution_cache[key]
                
    def _get_service_order(self, 
                          preferred_service: Optional[CaptchaService]) -> List[CaptchaService]:
        """Get ordered list of services to try"""
        if preferred_service and preferred_service in self.service_configs:
            services = [preferred_service]
            services.extend([s for s in self.service_priorities if s != preferred_service])
        else:
            services = self.service_priorities.copy()
            
        # Filter by configured services
        return [s for s in services if s in self.service_configs]
        
    def _is_service_available(self, service: CaptchaService) -> bool:
        """Check if service is available and not rate limited"""
        if service not in self.service_configs:
            return False
            
        config = self.service_configs[service]
        if not config.get('enabled', True):
            return False
            
        # Check rate limiting
        if service in self.rate_limits:
            limit_time = self.rate_limits[service]
            if time.time() < limit_time:
                return False
                
        return True
        
    def _update_stats(self, 
                     service: Optional[CaptchaService],
                     result: CaptchaResult,
                     success: bool):
        """Update service statistics"""
        if success:
            self.stats['total_solved'] += 1
            if service:
                if service.value not in self.stats['service_usage']:
                    self.stats['service_usage'][service.value] = 0
                self.stats['service_usage'][service.value] += 1
                
        # Update success rate
        total_attempts = sum(self.stats['service_usage'].values()) + (0 if success else 1)
        if total_attempts > 0:
            self.stats['success_rate'] = (self.stats['total_solved'] / total_attempts) * 100
            
    async def get_balance(self, service: CaptchaService) -> float:
        """Get account balance for service"""
        if service not in self.service_configs:
            return 0.0
            
        config = self.service_configs[service]
        
        try:
            async with aiohttp.ClientSession() as session:
                if service == CaptchaService.TWOCAPTCHA:
                    url = config['balance_url'].format(config['api_key'])
                    async with session.get(url) as response:
                        result = await response.text()
                        return float(result) if result.replace('.', '').isdigit() else 0.0
                        
                elif service in [CaptchaService.ANTICAPTCHA, CaptchaService.CAPMONSTER]:
                    data = {'clientKey': config['api_key']}
                    url = f"{config['base_url']}/getBalance"
                    async with session.post(url, json=data) as response:
                        result = await response.json()
                        return result.get('balance', 0.0)
                        
        except Exception as e:
            self.logger.error(f"Failed to get balance for {service.value}: {e}")
            
        return 0.0
        
    async def solve_image_captcha(self, 
                                 image_path: str,
                                 **kwargs) -> CaptchaResult:
        """Convenience method for image captcha"""
        captcha_data = {'image_path': image_path}
        captcha_data.update(kwargs)
        
        return await self.solve_captcha(
            CaptchaType.IMAGE,
            captcha_data
        )
        
    async def solve_recaptcha_v2(self, 
                                sitekey: str,
                                page_url: str,
                                **kwargs) -> CaptchaResult:
        """Convenience method for reCAPTCHA v2"""
        captcha_data = {
            'sitekey': sitekey,
            'page_url': page_url
        }
        captcha_data.update(kwargs)
        
        return await self.solve_captcha(
            CaptchaType.RECAPTCHA_V2,
            captcha_data
        )
        
    async def solve_recaptcha_v3(self, 
                                sitekey: str,
                                page_url: str,
                                action: str = 'verify',
                                min_score: float = 0.3,
                                **kwargs) -> CaptchaResult:
        """Convenience method for reCAPTCHA v3"""
        captcha_data = {
            'sitekey': sitekey,
            'page_url': page_url,
            'action': action,
            'min_score': min_score
        }
        captcha_data.update(kwargs)
        
        return await self.solve_captcha(
            CaptchaType.RECAPTCHA_V3,
            captcha_data
        )
        
    def clear_cache(self):
        """Clear solution cache"""
        self.solution_cache.clear()
        self.stats['cache_hits'] = 0
        self.logger.info("Cleared captcha solution cache")
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get solver statistics"""
        return self.stats.copy()
        
    def export_config(self, output_path: str):
        """Export service configurations"""
        export_data = {}
        
        for service, config in self.service_configs.items():
            # Don't export API keys in plain text
            safe_config = config.copy()
            if 'api_key' in safe_config:
                safe_config['api_key'] = '***HIDDEN***'
            export_data[service.value] = safe_config
            
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        self.logger.info(f"Exported captcha config to {output_path}")
        
    def disable_service(self, service: CaptchaService, duration: int = 300):
        """Temporarily disable a service"""
        if service in self.service_configs:
            self.rate_limits[service] = time.time() + duration
            self.logger.warning(f"Disabled {service.value} for {duration} seconds")