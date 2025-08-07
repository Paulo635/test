"""
Advanced Config Parser for OpenBullet Python
Parses .loli config files and translates LoliScript to executable Python
"""

import re
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

class BlockType(Enum):
    REQUEST = "REQUEST"
    PARSE = "PARSE"
    FUNCTION = "FUNCTION"
    UTILITY = "UTILITY"
    CAPTCHA = "CAPTCHA"
    CONDITION = "IF"
    LOOP = "FOR"
    VARIABLE = "SET"
    SCRIPT = "SCRIPT"

class RequestMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

@dataclass
class ConfigVariable:
    """Config variable definition"""
    name: str
    value: Any
    is_global: bool = False
    description: str = ""

@dataclass
class ConfigBlock:
    """Represents a single block in LoliScript"""
    block_type: BlockType
    label: str = ""
    content: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    disabled: bool = False
    
class ParsedConfig:
    """Complete parsed config with metadata and blocks"""
    
    def __init__(self):
        self.metadata = {}
        self.settings = {}
        self.variables = {}
        self.blocks = []
        self.custom_functions = {}
        self.imports = []

class ConfigParser:
    """
    Advanced LoliScript config parser that converts .loli files
    to executable Python structures
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # LoliScript command patterns
        self.block_patterns = {
            'metadata': re.compile(r'#METADATA\s*\n(.*?)(?=#\w+|\Z)', re.DOTALL),
            'settings': re.compile(r'#SETTINGS\s*\n(.*?)(?=#\w+|\Z)', re.DOTALL),
            'script': re.compile(r'#SCRIPT\s*\n(.*?)(?=#\w+|\Z)', re.DOTALL)
        }
        
        # Block command patterns
        self.command_patterns = {
            'request': re.compile(r'REQUEST\s+(\w+)\s+"([^"]+)"(?:\s+(.*))?', re.IGNORECASE),
            'parse': re.compile(r'PARSE\s+"([^"]+)"\s+LR\s+"([^"]+)"\s+"([^"]+)"(?:\s+(.*))?', re.IGNORECASE),
            'function': re.compile(r'FUNCTION\s+(\w+)(?:\s+"([^"]+)")?(?:\s+(.*))?', re.IGNORECASE),
            'set': re.compile(r'SET\s+VAR\s+"([^"]+)"\s+"([^"]*)"(?:\s+(.*))?', re.IGNORECASE),
            'if': re.compile(r'IF\s+(.+)', re.IGNORECASE),
            'endif': re.compile(r'ENDIF', re.IGNORECASE),
            'for': re.compile(r'FOR\s+(.+)', re.IGNORECASE),
            'endfor': re.compile(r'ENDFOR', re.IGNORECASE)
        }
        
        # Function mappings
        self.function_mappings = {
            'Hash': self._parse_hash_function,
            'Base64Encode': self._parse_base64_function,
            'Base64Decode': self._parse_base64_function,
            'RegexMatch': self._parse_regex_function,
            'Replace': self._parse_replace_function,
            'RandomString': self._parse_random_function,
            'Timestamp': self._parse_timestamp_function,
            'ComputeHash': self._parse_hash_function,
            'HTMLDecode': self._parse_html_function,
            'URLEncode': self._parse_url_function,
            'URLDecode': self._parse_url_function
        }
        
    def parse_config(self, file_path: str) -> ParsedConfig:
        """
        Parse a .loli config file
        
        Args:
            file_path: Path to .loli config file
            
        Returns:
            ParsedConfig object with parsed content
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
            
        try:
            content = path.read_text(encoding='utf-8')
            
            config = ParsedConfig()
            
            # Parse main sections
            self._parse_metadata(content, config)
            self._parse_settings(content, config)
            self._parse_script(content, config)
            
            self.logger.info(f"Parsed config '{path.name}' with {len(config.blocks)} blocks")
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to parse config {file_path}: {e}")
            raise
            
    def _parse_metadata(self, content: str, config: ParsedConfig):
        """Parse metadata section"""
        match = self.block_patterns['metadata'].search(content)
        if not match:
            return
            
        metadata_content = match.group(1).strip()
        
        for line in metadata_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
                
            if '=' in line:
                key, value = line.split('=', 1)
                config.metadata[key.strip()] = self._parse_value(value.strip())
                
    def _parse_settings(self, content: str, config: ParsedConfig):
        """Parse settings section"""
        match = self.block_patterns['settings'].search(content)
        if not match:
            return
            
        settings_content = match.group(1).strip()
        
        for line in settings_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
                
            if '=' in line:
                key, value = line.split('=', 1)
                config.settings[key.strip()] = self._parse_value(value.strip())
                
    def _parse_script(self, content: str, config: ParsedConfig):
        """Parse script section with LoliScript blocks"""
        match = self.block_patterns['script'].search(content)
        if not match:
            return
            
        script_content = match.group(1).strip()
        lines = script_content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line or line.startswith('//'):
                i += 1
                continue
                
            # Parse block
            block, consumed_lines = self._parse_block(lines[i:])
            if block:
                config.blocks.append(block)
                
            i += max(1, consumed_lines)
            
    def _parse_block(self, lines: List[str]) -> Tuple[Optional[ConfigBlock], int]:
        """Parse a single LoliScript block"""
        if not lines:
            return None, 0
            
        first_line = lines[0].strip()
        consumed_lines = 1
        
        # Check for block label
        label = ""
        if first_line.startswith('LABEL:'):
            label = first_line[6:].strip()
            if len(lines) > 1:
                first_line = lines[1].strip()
                consumed_lines = 2
            else:
                return None, 1
                
        # Parse different block types
        if first_line.startswith('REQUEST'):
            return self._parse_request_block(first_line, label, lines[consumed_lines-1:])
        elif first_line.startswith('PARSE'):
            return self._parse_parse_block(first_line, label)
        elif first_line.startswith('FUNCTION'):
            return self._parse_function_block(first_line, label)
        elif first_line.startswith('SET'):
            return self._parse_set_block(first_line, label)
        elif first_line.startswith('IF'):
            return self._parse_if_block(lines, label)
        elif first_line.startswith('FOR'):
            return self._parse_for_block(lines, label)
        else:
            # Unknown block type, treat as script
            return ConfigBlock(
                block_type=BlockType.SCRIPT,
                label=label,
                content=first_line
            ), 1
            
    def _parse_request_block(self, line: str, label: str, remaining_lines: List[str]) -> Tuple[ConfigBlock, int]:
        """Parse REQUEST block"""
        match = self.command_patterns['request'].match(line)
        if not match:
            return None, 1
            
        method = match.group(1).upper()
        url = match.group(2)
        options = match.group(3) or ""
        
        block = ConfigBlock(
            block_type=BlockType.REQUEST,
            label=label,
            content=line,
            parameters={
                'method': method,
                'url': url,
                'headers': {},
                'data': '',
                'params': {},
                'cookies': {},
                'auth': None,
                'timeout': 30,
                'follow_redirects': True
            }
        )
        
        # Parse options
        self._parse_request_options(options, block.parameters)
        
        # Parse additional lines for headers, data, etc.
        consumed = 1
        for i, line in enumerate(remaining_lines[1:], 1):
            line = line.strip()
            if not line or line.startswith('//'):
                consumed += 1
                continue
            elif line.startswith('HEADER'):
                self._parse_header_line(line, block.parameters)
                consumed += 1
            elif line.startswith('DATA'):
                self._parse_data_line(line, block.parameters)
                consumed += 1
            elif line.startswith('COOKIE'):
                self._parse_cookie_line(line, block.parameters)
                consumed += 1
            else:
                break
                
        return block, consumed
        
    def _parse_parse_block(self, line: str, label: str) -> Tuple[ConfigBlock, int]:
        """Parse PARSE block"""
        match = self.command_patterns['parse'].match(line)
        if not match:
            return None, 1
            
        variable = match.group(1)
        left_delimiter = match.group(2)
        right_delimiter = match.group(3)
        options = match.group(4) or ""
        
        block = ConfigBlock(
            block_type=BlockType.PARSE,
            label=label,
            content=line,
            parameters={
                'variable': variable,
                'left_delimiter': left_delimiter,
                'right_delimiter': right_delimiter,
                'source': 'SOURCE',
                'options': options
            }
        )
        
        return block, 1
        
    def _parse_function_block(self, line: str, label: str) -> Tuple[ConfigBlock, int]:
        """Parse FUNCTION block"""
        match = self.command_patterns['function'].match(line)
        if not match:
            return None, 1
            
        function_name = match.group(1)
        variable = match.group(2) or ""
        arguments = match.group(3) or ""
        
        block = ConfigBlock(
            block_type=BlockType.FUNCTION,
            label=label,
            content=line,
            parameters={
                'function': function_name,
                'variable': variable,
                'arguments': self._parse_function_arguments(arguments)
            }
        )
        
        return block, 1
        
    def _parse_set_block(self, line: str, label: str) -> Tuple[ConfigBlock, int]:
        """Parse SET block"""
        match = self.command_patterns['set'].match(line)
        if not match:
            return None, 1
            
        variable = match.group(1)
        value = match.group(2)
        options = match.group(3) or ""
        
        block = ConfigBlock(
            block_type=BlockType.VARIABLE,
            label=label,
            content=line,
            parameters={
                'variable': variable,
                'value': value,
                'options': options
            }
        )
        
        return block, 1
        
    def _parse_if_block(self, lines: List[str], label: str) -> Tuple[ConfigBlock, int]:
        """Parse IF block with nested content"""
        if_line = lines[0].strip()
        match = self.command_patterns['if'].match(if_line)
        if not match:
            return None, 1
            
        condition = match.group(1)
        
        # Find matching ENDIF
        nested_ifs = 0
        endif_index = -1
        
        for i, line in enumerate(lines[1:], 1):
            line_stripped = line.strip().upper()
            if line_stripped.startswith('IF '):
                nested_ifs += 1
            elif line_stripped == 'ENDIF':
                if nested_ifs == 0:
                    endif_index = i
                    break
                else:
                    nested_ifs -= 1
                    
        if endif_index == -1:
            self.logger.warning("No matching ENDIF found for IF block")
            return None, 1
            
        # Parse nested blocks
        nested_content = lines[1:endif_index]
        nested_blocks = []
        
        i = 0
        while i < len(nested_content):
            block, consumed = self._parse_block(nested_content[i:])
            if block:
                nested_blocks.append(block)
            i += max(1, consumed)
            
        block = ConfigBlock(
            block_type=BlockType.CONDITION,
            label=label,
            content=if_line,
            parameters={
                'condition': condition,
                'nested_blocks': nested_blocks
            }
        )
        
        return block, endif_index + 1
        
    def _parse_for_block(self, lines: List[str], label: str) -> Tuple[ConfigBlock, int]:
        """Parse FOR loop block"""
        for_line = lines[0].strip()
        match = self.command_patterns['for'].match(for_line)
        if not match:
            return None, 1
            
        loop_definition = match.group(1)
        
        # Find matching ENDFOR
        nested_fors = 0
        endfor_index = -1
        
        for i, line in enumerate(lines[1:], 1):
            line_stripped = line.strip().upper()
            if line_stripped.startswith('FOR '):
                nested_fors += 1
            elif line_stripped == 'ENDFOR':
                if nested_fors == 0:
                    endfor_index = i
                    break
                else:
                    nested_fors -= 1
                    
        if endfor_index == -1:
            self.logger.warning("No matching ENDFOR found for FOR block")
            return None, 1
            
        # Parse nested blocks
        nested_content = lines[1:endfor_index]
        nested_blocks = []
        
        i = 0
        while i < len(nested_content):
            block, consumed = self._parse_block(nested_content[i:])
            if block:
                nested_blocks.append(block)
            i += max(1, consumed)
            
        block = ConfigBlock(
            block_type=BlockType.LOOP,
            label=label,
            content=for_line,
            parameters={
                'loop_definition': loop_definition,
                'nested_blocks': nested_blocks
            }
        )
        
        return block, endfor_index + 1
        
    def _parse_request_options(self, options: str, parameters: Dict):
        """Parse REQUEST block options"""
        if not options:
            return
            
        # Parse various options
        option_patterns = {
            'timeout': re.compile(r'TIMEOUT\s+(\d+)', re.IGNORECASE),
            'redirect': re.compile(r'REDIRECT\s+(TRUE|FALSE)', re.IGNORECASE),
            'encoding': re.compile(r'ENCODING\s+"([^"]+)"', re.IGNORECASE)
        }
        
        for option, pattern in option_patterns.items():
            match = pattern.search(options)
            if match:
                if option == 'timeout':
                    parameters['timeout'] = int(match.group(1))
                elif option == 'redirect':
                    parameters['follow_redirects'] = match.group(1).upper() == 'TRUE'
                elif option == 'encoding':
                    parameters['encoding'] = match.group(1)
                    
    def _parse_header_line(self, line: str, parameters: Dict):
        """Parse HEADER line"""
        header_pattern = re.compile(r'HEADER\s+"([^"]+)"\s+"([^"]*)"', re.IGNORECASE)
        match = header_pattern.match(line)
        if match:
            header_name = match.group(1)
            header_value = match.group(2)
            parameters['headers'][header_name] = header_value
            
    def _parse_data_line(self, line: str, parameters: Dict):
        """Parse DATA line"""
        data_pattern = re.compile(r'DATA\s+"([^"]*)"', re.IGNORECASE)
        match = data_pattern.match(line)
        if match:
            parameters['data'] = match.group(1)
            
    def _parse_cookie_line(self, line: str, parameters: Dict):
        """Parse COOKIE line"""
        cookie_pattern = re.compile(r'COOKIE\s+"([^"]+)"\s+"([^"]*)"', re.IGNORECASE)
        match = cookie_pattern.match(line)
        if match:
            cookie_name = match.group(1)
            cookie_value = match.group(2)
            parameters['cookies'][cookie_name] = cookie_value
            
    def _parse_function_arguments(self, arguments: str) -> List[str]:
        """Parse function arguments"""
        if not arguments:
            return []
            
        # Simple argument parsing (could be enhanced)
        args = []
        current_arg = ""
        in_quotes = False
        
        for char in arguments:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ' ' and not in_quotes:
                if current_arg:
                    args.append(current_arg.strip('"'))
                    current_arg = ""
            else:
                current_arg += char
                
        if current_arg:
            args.append(current_arg.strip('"'))
            
        return args
        
    def _parse_value(self, value: str) -> Any:
        """Parse configuration value"""
        value = value.strip()
        
        # Remove quotes
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            return value[1:-1]
            
        # Try to parse as number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
            
        # Try to parse as boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
            
        return value
        
    def _parse_hash_function(self, arguments: List[str]) -> Dict:
        """Parse hash function parameters"""
        return {
            'algorithm': arguments[0] if arguments else 'md5',
            'input': arguments[1] if len(arguments) > 1 else '',
            'encoding': arguments[2] if len(arguments) > 2 else 'utf-8'
        }
        
    def _parse_base64_function(self, arguments: List[str]) -> Dict:
        """Parse base64 function parameters"""
        return {
            'input': arguments[0] if arguments else '',
            'encoding': arguments[1] if len(arguments) > 1 else 'utf-8'
        }
        
    def _parse_regex_function(self, arguments: List[str]) -> Dict:
        """Parse regex function parameters"""
        return {
            'pattern': arguments[0] if arguments else '',
            'input': arguments[1] if len(arguments) > 1 else '',
            'group': int(arguments[2]) if len(arguments) > 2 and arguments[2].isdigit() else 0
        }
        
    def _parse_replace_function(self, arguments: List[str]) -> Dict:
        """Parse replace function parameters"""
        return {
            'input': arguments[0] if arguments else '',
            'old': arguments[1] if len(arguments) > 1 else '',
            'new': arguments[2] if len(arguments) > 2 else ''
        }
        
    def _parse_random_function(self, arguments: List[str]) -> Dict:
        """Parse random string function parameters"""
        return {
            'length': int(arguments[0]) if arguments and arguments[0].isdigit() else 10,
            'charset': arguments[1] if len(arguments) > 1 else 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        }
        
    def _parse_timestamp_function(self, arguments: List[str]) -> Dict:
        """Parse timestamp function parameters"""
        return {
            'format': arguments[0] if arguments else 'unix',
            'timezone': arguments[1] if len(arguments) > 1 else 'UTC'
        }
        
    def _parse_html_function(self, arguments: List[str]) -> Dict:
        """Parse HTML decode function parameters"""
        return {
            'input': arguments[0] if arguments else ''
        }
        
    def _parse_url_function(self, arguments: List[str]) -> Dict:
        """Parse URL encode/decode function parameters"""
        return {
            'input': arguments[0] if arguments else '',
            'encoding': arguments[1] if len(arguments) > 1 else 'utf-8'
        }
        
    def export_config(self, config: ParsedConfig, output_path: str, format_type: str = 'loli') -> bool:
        """
        Export parsed config back to file
        
        Args:
            config: ParsedConfig object
            output_path: Output file path
            format_type: 'loli' or 'json'
            
        Returns:
            True if export successful
        """
        try:
            if format_type == 'json':
                self._export_json_config(config, output_path)
            else:
                self._export_loli_config(config, output_path)
                
            self.logger.info(f"Exported config to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export config: {e}")
            return False
            
    def _export_json_config(self, config: ParsedConfig, output_path: str):
        """Export config as JSON"""
        export_data = {
            'metadata': config.metadata,
            'settings': config.settings,
            'variables': config.variables,
            'blocks': []
        }
        
        for block in config.blocks:
            block_data = {
                'type': block.block_type.value,
                'label': block.label,
                'content': block.content,
                'parameters': block.parameters,
                'conditions': block.conditions,
                'disabled': block.disabled
            }
            export_data['blocks'].append(block_data)
            
        Path(output_path).write_text(json.dumps(export_data, indent=2), encoding='utf-8')
        
    def _export_loli_config(self, config: ParsedConfig, output_path: str):
        """Export config as .loli format"""
        lines = []
        
        # Metadata section
        if config.metadata:
            lines.append("#METADATA")
            for key, value in config.metadata.items():
                lines.append(f"{key} = {self._format_value(value)}")
            lines.append("")
            
        # Settings section
        if config.settings:
            lines.append("#SETTINGS")
            for key, value in config.settings.items():
                lines.append(f"{key} = {self._format_value(value)}")
            lines.append("")
            
        # Script section
        lines.append("#SCRIPT")
        for block in config.blocks:
            lines.extend(self._format_block(block))
            lines.append("")
            
        Path(output_path).write_text('\n'.join(lines), encoding='utf-8')
        
    def _format_value(self, value: Any) -> str:
        """Format value for .loli export"""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value).lower()
        else:
            return str(value)
            
    def _format_block(self, block: ConfigBlock) -> List[str]:
        """Format block for .loli export"""
        lines = []
        
        if block.label:
            lines.append(f"LABEL:{block.label}")
            
        if block.block_type == BlockType.REQUEST:
            lines.append(f"REQUEST {block.parameters['method']} \"{block.parameters['url']}\"")
            
            for name, value in block.parameters.get('headers', {}).items():
                lines.append(f"HEADER \"{name}\" \"{value}\"")
                
            if block.parameters.get('data'):
                lines.append(f"DATA \"{block.parameters['data']}\"")
                
            for name, value in block.parameters.get('cookies', {}).items():
                lines.append(f"COOKIE \"{name}\" \"{value}\"")
                
        elif block.block_type == BlockType.PARSE:
            params = block.parameters
            lines.append(f"PARSE \"{params['variable']}\" LR \"{params['left_delimiter']}\" \"{params['right_delimiter']}\"")
            
        elif block.block_type == BlockType.FUNCTION:
            params = block.parameters
            args = ' '.join(f'"{arg}"' for arg in params.get('arguments', []))
            lines.append(f"FUNCTION {params['function']} \"{params.get('variable', '')}\" {args}")
            
        elif block.block_type == BlockType.VARIABLE:
            params = block.parameters
            lines.append(f"SET VAR \"{params['variable']}\" \"{params['value']}\"")
            
        elif block.block_type == BlockType.CONDITION:
            lines.append(f"IF {block.parameters['condition']}")
            for nested_block in block.parameters.get('nested_blocks', []):
                nested_lines = self._format_block(nested_block)
                lines.extend([f"  {line}" for line in nested_lines])
            lines.append("ENDIF")
            
        elif block.block_type == BlockType.LOOP:
            lines.append(f"FOR {block.parameters['loop_definition']}")
            for nested_block in block.parameters.get('nested_blocks', []):
                nested_lines = self._format_block(nested_block)
                lines.extend([f"  {line}" for line in nested_lines])
            lines.append("ENDFOR")
            
        else:
            lines.append(block.content)
            
        return lines
        
    def validate_config(self, config: ParsedConfig) -> List[str]:
        """
        Validate parsed config for common issues
        
        Returns:
            List of validation errors/warnings
        """
        issues = []
        
        # Check for required metadata
        required_metadata = ['Name', 'Author', 'Category']
        for field in required_metadata:
            if field not in config.metadata:
                issues.append(f"Missing required metadata field: {field}")
                
        # Check for valid block sequences
        for i, block in enumerate(config.blocks):
            if block.block_type == BlockType.PARSE:
                # PARSE blocks should come after REQUEST blocks
                if i == 0 or config.blocks[i-1].block_type != BlockType.REQUEST:
                    issues.append(f"PARSE block at position {i} not preceded by REQUEST block")
                    
            elif block.block_type == BlockType.REQUEST:
                params = block.parameters
                if not params.get('url'):
                    issues.append(f"REQUEST block at position {i} missing URL")
                    
        return issues