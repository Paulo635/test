"""
Advanced Wordlist Manager for OpenBullet Python
Handles wordlists, combo lists, filtering, and data processing
"""

import asyncio
import random
import re
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Iterator, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import csv
import gzip
import logging
from itertools import islice
import hashlib

class WordlistType(Enum):
    SIMPLE = "simple"           # One item per line
    COMBO = "combo"             # username:password format
    EMAIL_PASS = "email_pass"   # email:password format
    CUSTOM = "custom"           # Custom separator
    JSON = "json"               # JSON format
    CSV = "csv"                # CSV format

@dataclass
class WordlistEntry:
    """Single wordlist entry with metadata"""
    data: Union[str, Dict, List]
    line_number: int = 0
    source_file: str = ""
    processed: bool = False
    
    @property
    def as_combo(self) -> Tuple[str, str]:
        """Extract as username:password combo"""
        if isinstance(self.data, str):
            if ':' in self.data:
                parts = self.data.split(':', 1)
                return parts[0], parts[1]
            else:
                return self.data, ""
        return str(self.data), ""
        
    @property
    def as_string(self) -> str:
        """Convert to string representation"""
        if isinstance(self.data, str):
            return self.data
        elif isinstance(self.data, dict):
            return json.dumps(self.data)
        elif isinstance(self.data, list):
            return ":".join(map(str, self.data))
        return str(self.data)

@dataclass
class WordlistStats:
    """Statistics for a wordlist"""
    total_entries: int = 0
    processed_entries: int = 0
    unique_entries: int = 0
    duplicate_entries: int = 0
    invalid_entries: int = 0
    file_size: int = 0
    load_time: float = 0.0
    
    @property
    def progress_percentage(self) -> float:
        """Calculate processing progress"""
        if self.total_entries == 0:
            return 0.0
        return (self.processed_entries / self.total_entries) * 100

@dataclass
class ManagedWordlist:
    """Wordlist with management metadata"""
    name: str
    file_path: str
    wordlist_type: WordlistType
    entries: List[WordlistEntry] = field(default_factory=list)
    stats: WordlistStats = field(default_factory=WordlistStats)
    tags: Set[str] = field(default_factory=set)
    separator: str = ":"
    encoding: str = "utf-8"
    is_loaded: bool = False
    
    def __len__(self):
        return len(self.entries)
        
    def __iter__(self):
        return iter(self.entries)

class WordlistManager:
    """
    Advanced wordlist management system with support for multiple formats,
    filtering, processing, and statistics tracking
    """
    
    def __init__(self, cache_enabled: bool = True, max_cache_size: int = 1000000):
        self.wordlists: Dict[str, ManagedWordlist] = {}
        self.cache_enabled = cache_enabled
        self.max_cache_size = max_cache_size
        self.global_stats = {
            'total_wordlists': 0,
            'total_entries': 0,
            'total_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Entry cache for fast lookups
        self.entry_cache: Dict[str, List[WordlistEntry]] = {}
        self.cache_usage = {}
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def load_wordlist(self, 
                     file_path: str, 
                     name: Optional[str] = None,
                     wordlist_type: WordlistType = WordlistType.SIMPLE,
                     separator: str = ":",
                     encoding: str = "utf-8",
                     tags: Set[str] = None) -> ManagedWordlist:
        """
        Load wordlist from file with comprehensive format support
        
        Args:
            file_path: Path to wordlist file
            name: Optional name for the wordlist
            wordlist_type: Type of wordlist format
            separator: Separator for combo/custom formats
            encoding: File encoding
            tags: Optional tags for categorization
            
        Returns:
            ManagedWordlist object
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Wordlist file not found: {file_path}")
            
        name = name or path.stem
        
        # Create wordlist object
        wordlist = ManagedWordlist(
            name=name,
            file_path=str(path),
            wordlist_type=wordlist_type,
            separator=separator,
            encoding=encoding,
            tags=tags or set()
        )
        
        # Load entries based on format
        import time
        start_time = time.time()
        
        try:
            if wordlist_type == WordlistType.JSON:
                self._load_json_wordlist(wordlist)
            elif wordlist_type == WordlistType.CSV:
                self._load_csv_wordlist(wordlist)
            else:
                self._load_text_wordlist(wordlist)
                
            wordlist.stats.load_time = time.time() - start_time
            wordlist.stats.file_size = path.stat().st_size
            wordlist.is_loaded = True
            
            # Store in manager
            self.wordlists[name] = wordlist
            self.global_stats['total_wordlists'] += 1
            self.global_stats['total_entries'] += len(wordlist.entries)
            
            self.logger.info(f"Loaded wordlist '{name}' with {len(wordlist.entries)} entries")
            
        except Exception as e:
            self.logger.error(f"Failed to load wordlist {file_path}: {e}")
            raise
            
        return wordlist
        
    def _load_text_wordlist(self, wordlist: ManagedWordlist):
        """Load text-based wordlist formats"""
        path = Path(wordlist.file_path)
        
        # Handle compressed files
        if path.suffix == '.gz':
            with gzip.open(path, 'rt', encoding=wordlist.encoding) as f:
                lines = f.readlines()
        else:
            with open(path, 'r', encoding=wordlist.encoding, errors='ignore') as f:
                lines = f.readlines()
                
        unique_entries = set()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Process based on type
            if wordlist.wordlist_type == WordlistType.COMBO:
                if ':' not in line:
                    wordlist.stats.invalid_entries += 1
                    continue
                    
            elif wordlist.wordlist_type == WordlistType.EMAIL_PASS:
                if ':' not in line or '@' not in line.split(':', 1)[0]:
                    wordlist.stats.invalid_entries += 1
                    continue
                    
            elif wordlist.wordlist_type == WordlistType.CUSTOM:
                if wordlist.separator not in line:
                    wordlist.stats.invalid_entries += 1
                    continue
                    
            # Check for duplicates
            line_hash = hashlib.md5(line.encode()).hexdigest()
            if line_hash in unique_entries:
                wordlist.stats.duplicate_entries += 1
                continue
                
            unique_entries.add(line_hash)
            
            # Create entry
            entry = WordlistEntry(
                data=line,
                line_number=line_num,
                source_file=wordlist.file_path
            )
            
            wordlist.entries.append(entry)
            
        wordlist.stats.total_entries = len(lines)
        wordlist.stats.unique_entries = len(unique_entries)
        
    def _load_json_wordlist(self, wordlist: ManagedWordlist):
        """Load JSON format wordlist"""
        path = Path(wordlist.file_path)
        
        with open(path, 'r', encoding=wordlist.encoding) as f:
            data = json.load(f)
            
        if isinstance(data, list):
            for i, item in enumerate(data):
                entry = WordlistEntry(
                    data=item,
                    line_number=i + 1,
                    source_file=wordlist.file_path
                )
                wordlist.entries.append(entry)
                
        wordlist.stats.total_entries = len(data)
        wordlist.stats.unique_entries = len(wordlist.entries)
        
    def _load_csv_wordlist(self, wordlist: ManagedWordlist):
        """Load CSV format wordlist"""
        path = Path(wordlist.file_path)
        
        with open(path, 'r', encoding=wordlist.encoding, newline='') as f:
            reader = csv.reader(f)
            
            for i, row in enumerate(reader):
                entry = WordlistEntry(
                    data=row,
                    line_number=i + 1,
                    source_file=wordlist.file_path
                )
                wordlist.entries.append(entry)
                
        wordlist.stats.total_entries = len(wordlist.entries)
        wordlist.stats.unique_entries = len(wordlist.entries)
        
    def get_wordlist(self, name: str) -> Optional[ManagedWordlist]:
        """Get wordlist by name"""
        return self.wordlists.get(name)
        
    def get_wordlist_names(self) -> List[str]:
        """Get list of loaded wordlist names"""
        return list(self.wordlists.keys())
        
    def remove_wordlist(self, name: str) -> bool:
        """Remove wordlist from manager"""
        if name in self.wordlists:
            wordlist = self.wordlists[name]
            self.global_stats['total_entries'] -= len(wordlist.entries)
            self.global_stats['total_wordlists'] -= 1
            
            # Clear from cache
            if name in self.entry_cache:
                del self.entry_cache[name]
                
            del self.wordlists[name]
            self.logger.info(f"Removed wordlist '{name}'")
            return True
        return False
        
    def filter_entries(self, 
                      wordlist_name: str,
                      filters: Dict,
                      limit: Optional[int] = None) -> List[WordlistEntry]:
        """
        Filter wordlist entries based on criteria
        
        Args:
            wordlist_name: Name of wordlist to filter
            filters: Dictionary of filter criteria
            limit: Maximum number of entries to return
            
        Supported filters:
            - regex: Regular expression pattern
            - contains: String that must be present
            - starts_with: String prefix
            - ends_with: String suffix
            - min_length: Minimum string length
            - max_length: Maximum string length
            - username_regex: Regex for username part (combo lists)
            - password_regex: Regex for password part (combo lists)
            - domain_filter: Email domain filter
            
        Returns:
            List of filtered WordlistEntry objects
        """
        wordlist = self.wordlists.get(wordlist_name)
        if not wordlist:
            return []
            
        # Check cache first
        cache_key = f"{wordlist_name}:{hash(str(filters))}"
        if self.cache_enabled and cache_key in self.entry_cache:
            self.global_stats['cache_hits'] += 1
            cached_entries = self.entry_cache[cache_key]
            return cached_entries[:limit] if limit else cached_entries
            
        self.global_stats['cache_misses'] += 1
        
        filtered_entries = []
        
        for entry in wordlist.entries:
            if self._matches_filters(entry, filters):
                filtered_entries.append(entry)
                if limit and len(filtered_entries) >= limit:
                    break
                    
        # Cache results
        if self.cache_enabled and len(filtered_entries) <= self.max_cache_size:
            self.entry_cache[cache_key] = filtered_entries
            self.cache_usage[cache_key] = 0
            
        return filtered_entries
        
    def _matches_filters(self, entry: WordlistEntry, filters: Dict) -> bool:
        """Check if entry matches filter criteria"""
        data_str = entry.as_string
        
        # Basic string filters
        if 'contains' in filters:
            if filters['contains'] not in data_str:
                return False
                
        if 'starts_with' in filters:
            if not data_str.startswith(filters['starts_with']):
                return False
                
        if 'ends_with' in filters:
            if not data_str.endswith(filters['ends_with']):
                return False
                
        if 'min_length' in filters:
            if len(data_str) < filters['min_length']:
                return False
                
        if 'max_length' in filters:
            if len(data_str) > filters['max_length']:
                return False
                
        # Regex filter
        if 'regex' in filters:
            try:
                if not re.search(filters['regex'], data_str):
                    return False
            except re.error:
                return False
                
        # Combo-specific filters
        if 'username_regex' in filters or 'password_regex' in filters:
            username, password = entry.as_combo
            
            if 'username_regex' in filters:
                try:
                    if not re.search(filters['username_regex'], username):
                        return False
                except re.error:
                    return False
                    
            if 'password_regex' in filters:
                try:
                    if not re.search(filters['password_regex'], password):
                        return False
                except re.error:
                    return False
                    
        # Email domain filter
        if 'domain_filter' in filters:
            username, _ = entry.as_combo
            if '@' in username:
                domain = username.split('@')[1]
                if domain != filters['domain_filter']:
                    return False
            else:
                return False
                
        return True
        
    def get_random_entries(self, 
                          wordlist_name: str, 
                          count: int = 1,
                          filters: Optional[Dict] = None) -> List[WordlistEntry]:
        """Get random entries from wordlist"""
        if filters:
            available_entries = self.filter_entries(wordlist_name, filters)
        else:
            wordlist = self.wordlists.get(wordlist_name)
            if not wordlist:
                return []
            available_entries = wordlist.entries
            
        if not available_entries:
            return []
            
        return random.sample(available_entries, min(count, len(available_entries)))
        
    def create_batch_iterator(self, 
                             wordlist_name: str,
                             batch_size: int = 100,
                             filters: Optional[Dict] = None,
                             shuffle: bool = False) -> Iterator[List[WordlistEntry]]:
        """
        Create iterator for processing wordlist in batches
        
        Args:
            wordlist_name: Name of wordlist
            batch_size: Number of entries per batch
            filters: Optional filter criteria
            shuffle: Whether to shuffle entries
            
        Yields:
            Batches of WordlistEntry objects
        """
        if filters:
            entries = self.filter_entries(wordlist_name, filters)
        else:
            wordlist = self.wordlists.get(wordlist_name)
            if not wordlist:
                return
            entries = wordlist.entries
            
        if shuffle:
            entries = entries.copy()
            random.shuffle(entries)
            
        # Create batches
        for i in range(0, len(entries), batch_size):
            yield entries[i:i + batch_size]
            
    def merge_wordlists(self, 
                       wordlist_names: List[str],
                       new_name: str,
                       remove_duplicates: bool = True) -> ManagedWordlist:
        """
        Merge multiple wordlists into a new one
        
        Args:
            wordlist_names: List of wordlist names to merge
            new_name: Name for the merged wordlist
            remove_duplicates: Whether to remove duplicate entries
            
        Returns:
            New ManagedWordlist object
        """
        merged_entries = []
        seen_hashes = set() if remove_duplicates else None
        all_tags = set()
        
        for name in wordlist_names:
            wordlist = self.wordlists.get(name)
            if not wordlist:
                continue
                
            all_tags.update(wordlist.tags)
            
            for entry in wordlist.entries:
                if remove_duplicates:
                    entry_hash = hashlib.md5(entry.as_string.encode()).hexdigest()
                    if entry_hash in seen_hashes:
                        continue
                    seen_hashes.add(entry_hash)
                    
                # Create new entry with updated source
                new_entry = WordlistEntry(
                    data=entry.data,
                    line_number=len(merged_entries) + 1,
                    source_file=f"merged_from_{name}"
                )
                merged_entries.append(new_entry)
                
        # Create merged wordlist
        merged_wordlist = ManagedWordlist(
            name=new_name,
            file_path=f"memory://merged_{new_name}",
            wordlist_type=WordlistType.SIMPLE,
            entries=merged_entries,
            tags=all_tags
        )
        
        merged_wordlist.stats.total_entries = len(merged_entries)
        merged_wordlist.stats.unique_entries = len(merged_entries)
        merged_wordlist.is_loaded = True
        
        self.wordlists[new_name] = merged_wordlist
        self.global_stats['total_wordlists'] += 1
        self.global_stats['total_entries'] += len(merged_entries)
        
        self.logger.info(f"Merged {len(wordlist_names)} wordlists into '{new_name}' with {len(merged_entries)} entries")
        return merged_wordlist
        
    def export_wordlist(self, 
                       wordlist_name: str,
                       output_path: str,
                       format_type: str = "text",
                       filters: Optional[Dict] = None,
                       include_stats: bool = False) -> bool:
        """
        Export wordlist to file
        
        Args:
            wordlist_name: Name of wordlist to export
            output_path: Output file path
            format_type: "text", "json", or "csv"
            filters: Optional filter criteria
            include_stats: Include statistics in output
            
        Returns:
            True if export successful
        """
        try:
            if filters:
                entries = self.filter_entries(wordlist_name, filters)
            else:
                wordlist = self.wordlists.get(wordlist_name)
                if not wordlist:
                    return False
                entries = wordlist.entries
                
            path = Path(output_path)
            
            if format_type == "json":
                data = []
                for entry in entries:
                    if isinstance(entry.data, str):
                        data.append(entry.data)
                    else:
                        data.append(entry.data)
                        
                if include_stats:
                    export_data = {
                        'entries': data,
                        'stats': wordlist.stats.__dict__ if wordlist else {}
                    }
                    path.write_text(json.dumps(export_data, indent=2), encoding='utf-8')
                else:
                    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
                    
            elif format_type == "csv":
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    if include_stats:
                        writer.writerow(['data', 'line_number', 'source_file'])
                        for entry in entries:
                            writer.writerow([entry.as_string, entry.line_number, entry.source_file])
                    else:
                        for entry in entries:
                            if isinstance(entry.data, list):
                                writer.writerow(entry.data)
                            else:
                                writer.writerow([entry.as_string])
                                
            else:  # text format
                lines = []
                for entry in entries:
                    line = entry.as_string
                    if include_stats:
                        line += f" # Line: {entry.line_number}, Source: {entry.source_file}"
                    lines.append(line)
                    
                path.write_text('\n'.join(lines), encoding='utf-8')
                
            self.logger.info(f"Exported {len(entries)} entries to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export wordlist: {e}")
            return False
            
    def get_statistics(self, wordlist_name: Optional[str] = None) -> Dict:
        """Get statistics for wordlist or global statistics"""
        if wordlist_name:
            wordlist = self.wordlists.get(wordlist_name)
            if not wordlist:
                return {}
                
            return {
                'name': wordlist.name,
                'file_path': wordlist.file_path,
                'type': wordlist.wordlist_type.value,
                'total_entries': wordlist.stats.total_entries,
                'unique_entries': wordlist.stats.unique_entries,
                'duplicate_entries': wordlist.stats.duplicate_entries,
                'invalid_entries': wordlist.stats.invalid_entries,
                'processed_entries': wordlist.stats.processed_entries,
                'progress_percentage': wordlist.stats.progress_percentage,
                'file_size': wordlist.stats.file_size,
                'load_time': wordlist.stats.load_time,
                'tags': list(wordlist.tags),
                'is_loaded': wordlist.is_loaded
            }
        else:
            return self.global_stats.copy()
            
    def mark_entry_processed(self, wordlist_name: str, entry_index: int):
        """Mark an entry as processed"""
        wordlist = self.wordlists.get(wordlist_name)
        if wordlist and 0 <= entry_index < len(wordlist.entries):
            if not wordlist.entries[entry_index].processed:
                wordlist.entries[entry_index].processed = True
                wordlist.stats.processed_entries += 1
                self.global_stats['total_processed'] += 1
                
    def reset_progress(self, wordlist_name: str):
        """Reset processing progress for wordlist"""
        wordlist = self.wordlists.get(wordlist_name)
        if wordlist:
            for entry in wordlist.entries:
                if entry.processed:
                    entry.processed = False
                    wordlist.stats.processed_entries -= 1
                    self.global_stats['total_processed'] -= 1
                    
    def search_entries(self, 
                      query: str,
                      wordlist_names: Optional[List[str]] = None,
                      case_sensitive: bool = False,
                      regex: bool = False,
                      limit: int = 100) -> List[Tuple[str, WordlistEntry]]:
        """
        Search for entries across wordlists
        
        Args:
            query: Search query
            wordlist_names: List of wordlist names to search (None for all)
            case_sensitive: Whether search is case sensitive
            regex: Whether query is a regex pattern
            limit: Maximum results to return
            
        Returns:
            List of tuples (wordlist_name, entry)
        """
        results = []
        search_lists = wordlist_names or list(self.wordlists.keys())
        
        for name in search_lists:
            wordlist = self.wordlists.get(name)
            if not wordlist:
                continue
                
            for entry in wordlist.entries:
                text = entry.as_string
                
                if not case_sensitive:
                    text = text.lower()
                    search_query = query.lower()
                else:
                    search_query = query
                    
                match_found = False
                
                if regex:
                    try:
                        if re.search(search_query, text):
                            match_found = True
                    except re.error:
                        continue
                else:
                    if search_query in text:
                        match_found = True
                        
                if match_found:
                    results.append((name, entry))
                    if len(results) >= limit:
                        return results
                        
        return results
        
    def clear_cache(self):
        """Clear entry cache"""
        self.entry_cache.clear()
        self.cache_usage.clear()
        self.global_stats['cache_hits'] = 0
        self.global_stats['cache_misses'] = 0
        self.logger.info("Cleared wordlist cache")
        
    def optimize_cache(self):
        """Remove least used cache entries"""
        if len(self.entry_cache) <= self.max_cache_size:
            return
            
        # Sort by usage count
        sorted_cache = sorted(self.cache_usage.items(), key=lambda x: x[1])
        
        # Remove least used entries
        remove_count = len(self.entry_cache) - self.max_cache_size
        for cache_key, _ in sorted_cache[:remove_count]:
            if cache_key in self.entry_cache:
                del self.entry_cache[cache_key]
            if cache_key in self.cache_usage:
                del self.cache_usage[cache_key]
                
        self.logger.info(f"Optimized cache, removed {remove_count} entries")