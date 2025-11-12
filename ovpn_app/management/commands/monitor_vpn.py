"""
Django management command to monitor VPN connections
Usage: python manage.py monitor_vpn [--interval 30] [--daemon]
"""

from django.core.management.base import BaseCommand
import time
import logging

from ovpn_app.vpn_monitor import sync_monitor_all_servers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor VPN connections and update database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Monitoring interval in seconds (default: 30)'
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run as daemon (continuous monitoring)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        daemon_mode = options['daemon']
        once = options['once']
        
        self.stdout.write(self.style.SUCCESS('Starting VPN connection monitor...'))
        
        if once:
            # Run once and exit
            self.stdout.write('Running single update...')
            try:
                sync_monitor_all_servers()
                self.stdout.write(self.style.SUCCESS('✓ Update completed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
                logger.error(f"Monitor error: {e}", exc_info=True)
            return
        
        # Continuous monitoring
        self.stdout.write(f'Monitoring interval: {interval} seconds')
        self.stdout.write('Press Ctrl+C to stop')
        
        try:
            while True:
                try:
                    self.stdout.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] Checking connections...')
                    sync_monitor_all_servers()
                    self.stdout.write(self.style.SUCCESS('✓ Update completed'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
                    logger.error(f"Monitor error: {e}", exc_info=True)
                
                if not daemon_mode:
                    break
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nMonitoring stopped by user'))
