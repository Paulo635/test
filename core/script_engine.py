"""
Script Engine for OpenBullet Python
Executes parsed configs with multi-threading, variable management, and flow control
"""

import asyncio
import random
import re
import hashlib
import base64
import urllib.parse
import html
import time
import string
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging
import json

from .config_parser import ParsedConfig, ConfigBlock, BlockType
from .http_client import HttpClient, HttpResponse
from .proxy_manager import ProxyManager
from .wordlist_manager import WordlistEntry
from utils.logger import Logger
from utils.crypto import CryptoManager

@dataclass
class ExecutionContext:
    """Context for script execution"""
    variables: Dict[str, Any]
    wordlist_entry: Optional[WordlistEntry]
    proxy_config: Optional[Any]
    http_client: HttpClient
    last_response: Optional[HttpResponse]
    loop_counters: Dict[str, int]
    
class ExecutionResult:
    """Result of config execution"""
    
    def __init__(self):
        self.status = "unknown"  # hit, fail, error, ban
        self.data = {}
        self.captured_variables = {}
        self.error_message = ""
        self.execution_time = 0.0
        self.proxy_used = None
        self.wordlist_entry = None

class ScriptEngine:
    """
    Advanced script execution engine that runs parsed configs
    with support for variables, conditions, loops, and multi-threading
    """
    
    def __init__(self, proxy_manager: ProxyManager, logger: Logger, crypto: CryptoManager):
        self.proxy_manager = proxy_manager
        self.logger = logger
        self.crypto = crypto
        
        # Built-in functions
        self.builtin_functions = {
            'Hash': self._function_hash,
            'Base64Encode': self._function_base64_encode,
            'Base64Decode': self._function_base64_decode,
            'RegexMatch': self._function_regex_match,
            'Replace': self._function_replace,
            'RandomString': self._function_random_string,
            'Timestamp': self._function_timestamp,
            'ComputeHash': self._function_hash,
            'HTMLDecode': self._function_html_decode,
            'URLEncode': self._function_url_encode,
            'URLDecode': self._function_url_decode,
            'Substring': self._function_substring,
            'Length': self._function_length,
            'ToLower': self._function_tolower,
            'ToUpper': self._function_toupper
        }
        
        # Execution statistics
        self.stats = {
            'total_executions': 0,
            'hits': 0,
            'fails': 0,
            'errors': 0,
            'bans': 0,
            'avg_execution_time': 0.0
        }
        
    async def execute_config(self, 
                           config: ParsedConfig, 
                           wordlist: List[WordlistEntry], 
                           threads: int = 10) -> Dict[str, List]:
        """
        Execute config against wordlist with multi-threading
        
        Args:
            config: Parsed config to execute
            wordlist: List of wordlist entries
            threads: Number of concurrent threads
            
        Returns:
            Dictionary with hits, fails, errors, and bans
        """
        start_time = time.time()
        
        results = {
            'hits': [],
            'fails': [],
            'errors': [],
            'bans': []
        }
        
        # Create semaphore for thread control
        semaphore = asyncio.Semaphore(threads)
        
        async def execute_entry(entry: WordlistEntry):
            async with semaphore:
                try:
                    result = await self._execute_single_entry(config, entry)
                    results[result.status].append({
                        'entry': entry.as_string,
                        'data': result.data,
                        'variables': result.captured_variables,
                        'execution_time': result.execution_time,
                        'proxy': result.proxy_used
                    })
                    
                    # Update statistics
                    self.stats['total_executions'] += 1
                    self.stats[result.status] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error executing entry {entry.as_string}: {e}")
                    results['errors'].append({
                        'entry': entry.as_string,
                        'error': str(e)
                    })
                    
        # Execute all entries concurrently
        tasks = [execute_entry(entry) for entry in wordlist]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update statistics
        total_time = time.time() - start_time
        if self.stats['total_executions'] > 0:
            self.stats['avg_execution_time'] = total_time / self.stats['total_executions']
            
        self.logger.info(f"Config execution complete: {len(results['hits'])} hits, "
                        f"{len(results['fails'])} fails, {len(results['errors'])} errors")
        
        return results
        
    async def _execute_single_entry(self, 
                                   config: ParsedConfig, 
                                   entry: WordlistEntry) -> ExecutionResult:
        """Execute config for a single wordlist entry"""
        start_time = time.time()
        
        result = ExecutionResult()
        result.wordlist_entry = entry
        
        # Get proxy if available
        proxy_config = self.proxy_manager.get_proxy() if self.proxy_manager else None
        result.proxy_used = proxy_config.to_url() if proxy_config else None
        
        # Create HTTP client
        async with HttpClient() as http_client:
            # Initialize execution context
            context = ExecutionContext(
                variables=self._initialize_variables(config, entry),
                wordlist_entry=entry,
                proxy_config=proxy_config,
                http_client=http_client,
                last_response=None,
                loop_counters={}
            )
            
            try:
                # Execute all blocks
                for block in config.blocks:
                    if block.disabled:
                        continue
                        
                    await self._execute_block(block, context)
                    
                # Determine result status
                result.status = self._determine_result_status(context)
                result.data = self._extract_result_data(context)
                result.captured_variables = context.variables.copy()
                
            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                self.logger.error(f"Execution error: {e}")
                
        result.execution_time = time.time() - start_time
        return result
        
    def _initialize_variables(self, 
                            config: ParsedConfig, 
                            entry: WordlistEntry) -> Dict[str, Any]:
        """Initialize execution variables"""
        variables = {
            'SOURCE': '',  # Last HTTP response content
            'HEADERS': {},  # Last response headers
            'STATUS': 0,   # Last response status code
            'COOKIES': {}, # Current cookies
            'ADDRESS': '',  # Last response URL
        }
        
        # Add config variables
        variables.update(config.variables)
        
        # Add wordlist data
        if entry:
            username, password = entry.as_combo
            variables['USER'] = username
            variables['PASS'] = password
            variables['DATA'] = entry.as_string
            
        # Add built-in variables
        variables['RANDOM'] = lambda: str(random.randint(1000, 9999))
        variables['TIMESTAMP'] = lambda: str(int(time.time()))
        
        return variables
        
    async def _execute_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute a single block"""
        self.logger.debug(f"Executing block: {block.block_type.value}")
        
        if block.block_type == BlockType.REQUEST:
            await self._execute_request_block(block, context)
        elif block.block_type == BlockType.PARSE:
            await self._execute_parse_block(block, context)
        elif block.block_type == BlockType.FUNCTION:
            await self._execute_function_block(block, context)
        elif block.block_type == BlockType.VARIABLE:
            await self._execute_variable_block(block, context)
        elif block.block_type == BlockType.CONDITION:
            await self._execute_condition_block(block, context)
        elif block.block_type == BlockType.LOOP:
            await self._execute_loop_block(block, context)
        else:
            self.logger.warning(f"Unknown block type: {block.block_type}")
            
    async def _execute_request_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute HTTP request block"""
        params = block.parameters
        
        # Substitute variables in URL
        url = self._substitute_variables(params['url'], context.variables)
        
        # Prepare headers
        headers = {}
        for name, value in params.get('headers', {}).items():
            headers[name] = self._substitute_variables(value, context.variables)
            
        # Prepare data
        data = self._substitute_variables(params.get('data', ''), context.variables)
        
        # Prepare cookies
        cookies = {}
        for name, value in params.get('cookies', {}).items():
            cookies[name] = self._substitute_variables(value, context.variables)
            
        try:
            # Make request
            response = await context.http_client.request(
                method=params['method'],
                url=url,
                headers=headers,
                data=data if data else None,
                proxy=context.proxy_config,
                auth=params.get('auth')
            )
            
            # Update context
            context.last_response = response
            context.variables['SOURCE'] = response.text
            context.variables['HEADERS'] = response.headers
            context.variables['STATUS'] = response.status_code
            context.variables['ADDRESS'] = response.url
            context.variables['COOKIES'].update(response.cookies)
            
            # Update proxy statistics
            if context.proxy_config:
                if 200 <= response.status_code < 400:
                    self.proxy_manager.mark_proxy_success(
                        context.proxy_config.host,
                        context.proxy_config.port,
                        response.elapsed
                    )
                else:
                    self.proxy_manager.mark_proxy_failed(
                        context.proxy_config.host,
                        context.proxy_config.port
                    )
                    
        except Exception as e:
            # Handle request errors
            if context.proxy_config:
                self.proxy_manager.mark_proxy_failed(
                    context.proxy_config.host,
                    context.proxy_config.port
                )
            raise e
            
    async def _execute_parse_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute parse block"""
        params = block.parameters
        
        variable_name = params['variable']
        left_delimiter = self._substitute_variables(params['left_delimiter'], context.variables)
        right_delimiter = self._substitute_variables(params['right_delimiter'], context.variables)
        source = context.variables.get('SOURCE', '')
        
        # Extract data between delimiters
        if left_delimiter in source and right_delimiter in source:
            start_index = source.find(left_delimiter) + len(left_delimiter)
            end_index = source.find(right_delimiter, start_index)
            
            if end_index != -1:
                extracted_value = source[start_index:end_index]
                context.variables[variable_name] = extracted_value
            else:
                context.variables[variable_name] = ''
        else:
            context.variables[variable_name] = ''
            
    async def _execute_function_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute function block"""
        params = block.parameters
        
        function_name = params['function']
        variable_name = params.get('variable', '')
        arguments = params.get('arguments', [])
        
        # Substitute variables in arguments
        substituted_args = []
        for arg in arguments:
            substituted_args.append(self._substitute_variables(arg, context.variables))
            
        # Execute function
        if function_name in self.builtin_functions:
            result = await self.builtin_functions[function_name](substituted_args, context)
            
            if variable_name:
                context.variables[variable_name] = result
        else:
            self.logger.warning(f"Unknown function: {function_name}")
            
    async def _execute_variable_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute variable assignment block"""
        params = block.parameters
        
        variable_name = params['variable']
        value = self._substitute_variables(params['value'], context.variables)
        
        context.variables[variable_name] = value
        
    async def _execute_condition_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute conditional block"""
        params = block.parameters
        
        condition = params['condition']
        nested_blocks = params.get('nested_blocks', [])
        
        # Evaluate condition
        if self._evaluate_condition(condition, context):
            # Execute nested blocks
            for nested_block in nested_blocks:
                await self._execute_block(nested_block, context)
                
    async def _execute_loop_block(self, block: ConfigBlock, context: ExecutionContext):
        """Execute loop block"""
        params = block.parameters
        
        loop_definition = params['loop_definition']
        nested_blocks = params.get('nested_blocks', [])
        
        # Parse loop definition (simplified)
        # Example: "i FROM 1 TO 10"
        loop_match = re.match(r'(\w+)\s+FROM\s+(\d+)\s+TO\s+(\d+)', loop_definition)
        if loop_match:
            var_name = loop_match.group(1)
            start_val = int(loop_match.group(2))
            end_val = int(loop_match.group(3))
            
            for i in range(start_val, end_val + 1):
                context.variables[var_name] = str(i)
                
                # Execute nested blocks
                for nested_block in nested_blocks:
                    await self._execute_block(nested_block, context)
                    
    def _substitute_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in text"""
        if not isinstance(text, str):
            return str(text)
            
        # Replace <variable> patterns
        def replace_var(match):
            var_name = match.group(1)
            if var_name in variables:
                value = variables[var_name]
                if callable(value):
                    return str(value())
                return str(value)
            return match.group(0)  # Return original if not found
            
        return re.sub(r'<(\w+)>', replace_var, text)
        
    def _evaluate_condition(self, condition: str, context: ExecutionContext) -> bool:
        """Evaluate a condition string"""
        # Substitute variables first
        condition = self._substitute_variables(condition, context.variables)
        
        # Simple condition evaluation
        # Example: "STATUS == 200"
        try:
            # Replace common operators
            condition = condition.replace('==', '==')
            condition = condition.replace('!=', '!=')
            condition = condition.replace('CONTAINS', 'in')
            
            # For safety, only allow specific variables and operators
            allowed_vars = ['STATUS', 'SOURCE', 'ADDRESS']
            safe_condition = condition
            
            for var in allowed_vars:
                if var in context.variables:
                    value = context.variables[var]
                    if isinstance(value, str):
                        safe_condition = safe_condition.replace(var, f'"{value}"')
                    else:
                        safe_condition = safe_condition.replace(var, str(value))
                        
            # Evaluate safely
            return eval(safe_condition)
            
        except Exception as e:
            self.logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False
            
    def _determine_result_status(self, context: ExecutionContext) -> str:
        """Determine the final status of execution"""
        # Check for common success indicators
        if context.last_response:
            status_code = context.last_response.status_code
            response_text = context.last_response.text.lower()
            
            # Check for success indicators
            success_indicators = ['success', 'welcome', 'dashboard', 'profile', 'account']
            fail_indicators = ['invalid', 'incorrect', 'wrong', 'error', 'failed', 'banned']
            
            # Status code based detection
            if status_code == 200:
                if any(indicator in response_text for indicator in success_indicators):
                    return "hits"
                elif any(indicator in response_text for indicator in fail_indicators):
                    return "fails"
                    
            # Rate limit / ban detection
            elif status_code in [429, 403]:
                return "bans"
            elif status_code >= 400:
                return "fails"
                
        return "fails"  # Default to fail
        
    def _extract_result_data(self, context: ExecutionContext) -> Dict[str, Any]:
        """Extract useful data from execution context"""
        data = {}
        
        # Extract captured variables (excluding built-ins)
        excluded_vars = ['SOURCE', 'HEADERS', 'STATUS', 'COOKIES', 'ADDRESS', 'USER', 'PASS', 'DATA']
        
        for key, value in context.variables.items():
            if key not in excluded_vars and not callable(value):
                data[key] = value
                
        return data
        
    # Built-in function implementations
    async def _function_hash(self, args: List[str], context: ExecutionContext) -> str:
        """Hash function"""
        algorithm = args[0] if args else 'md5'
        input_text = args[1] if len(args) > 1 else ''
        
        if algorithm.lower() == 'md5':
            return hashlib.md5(input_text.encode()).hexdigest()
        elif algorithm.lower() == 'sha1':
            return hashlib.sha1(input_text.encode()).hexdigest()
        elif algorithm.lower() == 'sha256':
            return hashlib.sha256(input_text.encode()).hexdigest()
        else:
            return hashlib.md5(input_text.encode()).hexdigest()
            
    async def _function_base64_encode(self, args: List[str], context: ExecutionContext) -> str:
        """Base64 encode function"""
        input_text = args[0] if args else ''
        return base64.b64encode(input_text.encode()).decode()
        
    async def _function_base64_decode(self, args: List[str], context: ExecutionContext) -> str:
        """Base64 decode function"""
        input_text = args[0] if args else ''
        try:
            return base64.b64decode(input_text).decode()
        except Exception:
            return ''
            
    async def _function_regex_match(self, args: List[str], context: ExecutionContext) -> str:
        """Regex match function"""
        pattern = args[0] if args else ''
        input_text = args[1] if len(args) > 1 else ''
        group = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
        
        try:
            match = re.search(pattern, input_text)
            if match:
                return match.group(group)
        except Exception:
            pass
        return ''
        
    async def _function_replace(self, args: List[str], context: ExecutionContext) -> str:
        """Replace function"""
        input_text = args[0] if args else ''
        old = args[1] if len(args) > 1 else ''
        new = args[2] if len(args) > 2 else ''
        
        return input_text.replace(old, new)
        
    async def _function_random_string(self, args: List[str], context: ExecutionContext) -> str:
        """Random string function"""
        length = int(args[0]) if args and args[0].isdigit() else 10
        charset = args[1] if len(args) > 1 else string.ascii_letters + string.digits
        
        return ''.join(random.choice(charset) for _ in range(length))
        
    async def _function_timestamp(self, args: List[str], context: ExecutionContext) -> str:
        """Timestamp function"""
        format_type = args[0] if args else 'unix'
        
        if format_type.lower() == 'unix':
            return str(int(time.time()))
        elif format_type.lower() == 'iso':
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        else:
            return str(int(time.time()))
            
    async def _function_html_decode(self, args: List[str], context: ExecutionContext) -> str:
        """HTML decode function"""
        input_text = args[0] if args else ''
        return html.unescape(input_text)
        
    async def _function_url_encode(self, args: List[str], context: ExecutionContext) -> str:
        """URL encode function"""
        input_text = args[0] if args else ''
        return urllib.parse.quote(input_text)
        
    async def _function_url_decode(self, args: List[str], context: ExecutionContext) -> str:
        """URL decode function"""
        input_text = args[0] if args else ''
        return urllib.parse.unquote(input_text)
        
    async def _function_substring(self, args: List[str], context: ExecutionContext) -> str:
        """Substring function"""
        input_text = args[0] if args else ''
        start = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        length = int(args[2]) if len(args) > 2 and args[2].isdigit() else len(input_text)
        
        return input_text[start:start + length]
        
    async def _function_length(self, args: List[str], context: ExecutionContext) -> str:
        """Length function"""
        input_text = args[0] if args else ''
        return str(len(input_text))
        
    async def _function_tolower(self, args: List[str], context: ExecutionContext) -> str:
        """To lower case function"""
        input_text = args[0] if args else ''
        return input_text.lower()
        
    async def _function_toupper(self, args: List[str], context: ExecutionContext) -> str:
        """To upper case function"""
        input_text = args[0] if args else ''
        return input_text.upper()
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return self.stats.copy()