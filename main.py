#!/usr/bin/env python3
"""
OpenBullet Python - Complete Automation and Credential Testing Tool
Author: AI Assistant
Version: 1.0.0

A complete Python reimplementation of OpenBullet with all original features:
- Config system with LoliScript support
- Advanced HTTP client with proxy support
- Multi-threading and parallel execution
- Captcha solving integration
- Comprehensive logging and reporting
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path

# Add core modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from core.script_engine import ScriptEngine
from core.config_parser import ConfigParser
from core.proxy_manager import ProxyManager
from core.wordlist_manager import WordlistManager
from utils.logger import Logger
from utils.crypto import CryptoManager

class OpenBulletPython:
    """
    Main OpenBullet Python application class
    Orchestrates all components and provides CLI interface
    """
    
    def __init__(self):
        self.logger = Logger()
        self.crypto = CryptoManager()
        self.proxy_manager = ProxyManager()
        self.wordlist_manager = WordlistManager()
        self.config_parser = ConfigParser()
        self.script_engine = ScriptEngine(
            proxy_manager=self.proxy_manager,
            logger=self.logger,
            crypto=self.crypto
        )
        
        # Create necessary directories
        self._create_directories()
        
    def _create_directories(self):
        """Create necessary project directories"""
        directories = [
            'configs', 'wordlists', 'proxies', 'logs', 
            'results', 'captcha_cache', 'data'
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
            
    def run_config(self, config_path, wordlist_path=None, proxy_list=None, threads=10):
        """
        Execute a config file with specified parameters
        
        Args:
            config_path (str): Path to config file (.loli or .opk)
            wordlist_path (str): Path to wordlist file
            proxy_list (str): Path to proxy list file
            threads (int): Number of threads to use
        """
        
        print(f"🚀 OpenBullet Python - Starting execution")
        print(f"📄 Config: {config_path}")
        print(f"📝 Wordlist: {wordlist_path}")
        print(f"🔗 Proxies: {proxy_list}")
        print(f"🧵 Threads: {threads}")
        print("-" * 50)
        
        try:
            # Load config
            config = self.config_parser.parse_config(config_path)
            self.logger.info(f"Loaded config: {config_path}")
            
            # Load wordlist
            if wordlist_path:
                wordlist = self.wordlist_manager.load_wordlist(wordlist_path)
                self.logger.info(f"Loaded {len(wordlist)} entries from wordlist")
            else:
                wordlist = []
                
            # Load proxies
            if proxy_list:
                proxies = self.proxy_manager.load_proxies(proxy_list)
                self.logger.info(f"Loaded {len(proxies)} proxies")
            
            # Execute config
            results = asyncio.run(
                self.script_engine.execute_config(
                    config, wordlist, threads=threads
                )
            )
            
            # Display results
            self._display_results(results)
            
        except Exception as e:
            self.logger.error(f"Execution failed: {str(e)}")
            print(f"❌ Error: {str(e)}")
            
    def _display_results(self, results):
        """Display execution results"""
        hits = results.get('hits', [])
        fails = results.get('fails', [])
        errors = results.get('errors', [])
        
        print("\n" + "="*50)
        print("📊 EXECUTION RESULTS")
        print("="*50)
        print(f"✅ Hits: {len(hits)}")
        print(f"❌ Fails: {len(fails)}")
        print(f"⚠️  Errors: {len(errors)}")
        
        if hits:
            print("\n🎯 HITS:")
            for hit in hits[:10]:  # Show first 10 hits
                print(f"  • {hit}")
            if len(hits) > 10:
                print(f"  ... and {len(hits) - 10} more")
                
    def interactive_mode(self):
        """Start interactive mode"""
        print("🎯 OpenBullet Python - Interactive Mode")
        print("Type 'help' for available commands")
        
        while True:
            try:
                command = input("\nOB-Python> ").strip()
                
                if command.lower() in ['exit', 'quit']:
                    print("👋 Goodbye!")
                    break
                elif command.lower() == 'help':
                    self._show_help()
                elif command.startswith('load'):
                    self._handle_load_command(command)
                elif command.startswith('run'):
                    self._handle_run_command(command)
                elif command.startswith('list'):
                    self._handle_list_command(command)
                else:
                    print("❓ Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                
    def _show_help(self):
        """Show help information"""
        help_text = """
🔧 Available Commands:

  load config <path>     - Load a config file
  load wordlist <path>   - Load a wordlist
  load proxies <path>    - Load proxy list
  
  run <config>          - Execute loaded config
  run <config> <wordlist> <proxies> - Execute with specific files
  
  list configs          - List available configs
  list wordlists        - List available wordlists
  list proxies          - List loaded proxies
  
  help                  - Show this help
  exit/quit             - Exit the program
        """
        print(help_text)
        
    def _handle_load_command(self, command):
        """Handle load commands"""
        parts = command.split()
        if len(parts) < 3:
            print("❌ Usage: load <type> <path>")
            return
            
        load_type = parts[1].lower()
        path = " ".join(parts[2:])
        
        try:
            if load_type == 'config':
                self.config_parser.parse_config(path)
                print(f"✅ Config loaded: {path}")
            elif load_type == 'wordlist':
                wordlist = self.wordlist_manager.load_wordlist(path)
                print(f"✅ Wordlist loaded: {len(wordlist)} entries")
            elif load_type == 'proxies':
                proxies = self.proxy_manager.load_proxies(path)
                print(f"✅ Proxies loaded: {len(proxies)} proxies")
            else:
                print("❌ Invalid type. Use: config, wordlist, or proxies")
        except Exception as e:
            print(f"❌ Error loading {load_type}: {str(e)}")
            
    def _handle_run_command(self, command):
        """Handle run commands"""
        parts = command.split()
        if len(parts) < 2:
            print("❌ Usage: run <config> [wordlist] [proxies]")
            return
            
        config_path = parts[1]
        wordlist_path = parts[2] if len(parts) > 2 else None
        proxy_path = parts[3] if len(parts) > 3 else None
        
        self.run_config(config_path, wordlist_path, proxy_path)
        
    def _handle_list_command(self, command):
        """Handle list commands"""
        parts = command.split()
        if len(parts) < 2:
            print("❌ Usage: list <type>")
            return
            
        list_type = parts[1].lower()
        
        if list_type == 'configs':
            configs = list(Path('configs').glob('*.loli')) + list(Path('configs').glob('*.opk'))
            print(f"📄 Available configs ({len(configs)}):")
            for config in configs:
                print(f"  • {config.name}")
        elif list_type == 'wordlists':
            wordlists = list(Path('wordlists').glob('*.txt'))
            print(f"📝 Available wordlists ({len(wordlists)}):")
            for wordlist in wordlists:
                print(f"  • {wordlist.name}")
        elif list_type == 'proxies':
            proxies = self.proxy_manager.get_active_proxies()
            print(f"🔗 Active proxies ({len(proxies)}):")
            for proxy in proxies[:10]:
                print(f"  • {proxy}")
            if len(proxies) > 10:
                print(f"  ... and {len(proxies) - 10} more")
        else:
            print("❌ Invalid type. Use: configs, wordlists, or proxies")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="OpenBullet Python - Complete Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py -i                              # Interactive mode
  python main.py -c config.loli -w wordlist.txt # Run config with wordlist
  python main.py -c config.loli -w wordlist.txt -p proxies.txt -t 20
        """
    )
    
    parser.add_argument('-c', '--config', help='Config file path (.loli or .opk)')
    parser.add_argument('-w', '--wordlist', help='Wordlist file path')
    parser.add_argument('-p', '--proxies', help='Proxy list file path')
    parser.add_argument('-t', '--threads', type=int, default=10, help='Number of threads (default: 10)')
    parser.add_argument('-i', '--interactive', action='store_true', help='Start interactive mode')
    parser.add_argument('--version', action='version', version='OpenBullet Python 1.0.0')
    
    args = parser.parse_args()
    
    # Create OpenBullet instance
    ob = OpenBulletPython()
    
    # Print banner
    print_banner()
    
    if args.interactive:
        ob.interactive_mode()
    elif args.config:
        ob.run_config(args.config, args.wordlist, args.proxies, args.threads)
    else:
        print("🎯 Use -i for interactive mode or provide -c with config file")
        print("Use --help for more options")

def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    OpenBullet Python v1.0.0                 ║
║              Complete Automation & Testing Tool             ║
║                                                              ║
║  🚀 Fast • 🔒 Secure • 🎯 Accurate • 🧵 Multi-threaded     ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

if __name__ == "__main__":
    main()