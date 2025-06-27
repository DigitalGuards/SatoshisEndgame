import asyncio
import signal
import sys
from typing import Optional

import click
import structlog
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import settings
from src.data.database import db
from src.services.monitoring_service import MonitoringService
from src.services.notification_service import DiscordNotificationService

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if settings.log_format == "plain" else structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
console = Console()


@click.group()
def cli():
    """SatoshisEndgame - Bitcoin Quantum Vulnerability Monitoring System"""
    pass


@cli.command()
@click.option('--test-webhook', is_flag=True, help='Send a test Discord webhook')
def monitor(test_webhook: bool):
    """Start the monitoring service"""
    console.print("[bold green]Starting SatoshisEndgame Monitoring System[/bold green]")
    
    async def run_monitor():
        monitoring_service = MonitoringService()
        
        try:
            # Initialize service
            with console.status("[bold yellow]Initializing services..."):
                await monitoring_service.initialize()
            
            # Test webhook if requested
            if test_webhook:
                console.print("[yellow]Sending test Discord webhook...[/yellow]")
                discord_service = DiscordNotificationService()
                success = await discord_service.send_test_alert()
                if success:
                    console.print("[green]✓ Test webhook sent successfully![/green]")
                else:
                    console.print("[red]✗ Failed to send test webhook[/red]")
                    return
            
            # Start monitoring
            await monitoring_service.start()
            console.print("[green]✓ Monitoring service started[/green]")
            console.print(f"[cyan]Monitoring {len(monitoring_service.monitored_addresses)} addresses[/cyan]")
            console.print("[dim]Press Ctrl+C to stop[/dim]")
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            await monitoring_service.stop()
            console.print("[green]✓ Monitoring service stopped[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.error("Monitor failed", error=str(e))
            await monitoring_service.stop()
            sys.exit(1)
    
    asyncio.run(run_monitor())


@cli.command()
def status():
    """Show monitoring system status"""
    async def show_status():
        try:
            await db.initialize()
            
            async with db.get_session() as session:
                # Get wallet stats
                from sqlalchemy import select, func
                from src.data.models import Wallet, Alert, Transaction
                
                total_wallets = await session.scalar(
                    select(func.count()).select_from(Wallet).where(Wallet.is_active == True)
                )
                
                vulnerable_wallets = await session.scalar(
                    select(func.count()).select_from(Wallet).where(
                        Wallet.is_vulnerable == True,
                        Wallet.is_active == True
                    )
                )
                
                total_balance = await session.scalar(
                    select(func.sum(Wallet.current_balance)).where(Wallet.is_active == True)
                ) or 0
                
                recent_alerts = await session.scalar(
                    select(func.count()).select_from(Alert).where(
                        Alert.created_at >= func.now() - func.cast('24 hours', func.INTERVAL)
                    )
                )
                
                # Create status table
                table = Table(title="SatoshisEndgame Status", show_header=True)
                table.add_column("Metric", style="cyan", no_wrap=True)
                table.add_column("Value", style="magenta")
                
                table.add_row("Total Wallets", str(total_wallets))
                table.add_row("Vulnerable Wallets", str(vulnerable_wallets))
                table.add_row("Total Balance (BTC)", f"{total_balance / 100_000_000:,.8f}")
                table.add_row("Alerts (24h)", str(recent_alerts))
                table.add_row("Database URL", settings.database_url.split('@')[-1])
                
                console.print(table)
                
            await db.close()
            
        except Exception as e:
            console.print(f"[red]Error getting status: {e}[/red]")
    
    asyncio.run(show_status())


@cli.command()
def init_db():
    """Initialize the database"""
    async def initialize():
        try:
            console.print("[yellow]Initializing database...[/yellow]")
            await db.initialize()
            await db.create_tables()
            console.print("[green]✓ Database initialized successfully![/green]")
            await db.close()
        except Exception as e:
            console.print(f"[red]Error initializing database: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(initialize())


@cli.command()
@click.confirmation_option(prompt='Are you sure you want to drop all tables?')
def drop_db():
    """Drop all database tables (CAUTION!)"""
    async def drop():
        try:
            console.print("[yellow]Dropping database tables...[/yellow]")
            await db.initialize()
            await db.drop_tables()
            console.print("[green]✓ Database tables dropped![/green]")
            await db.close()
        except Exception as e:
            console.print(f"[red]Error dropping tables: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(drop())


@cli.command()
@click.argument('address')
def check_address(address: str):
    """Check if an address is vulnerable"""
    from src.core.address_manager import AddressVulnerabilityDetector
    
    detector = AddressVulnerabilityDetector()
    
    # Basic validation
    if not (address.startswith('1') or address.startswith('3') or address.startswith('bc1')):
        console.print("[red]Invalid Bitcoin address format[/red]")
        return
    
    # Check vulnerability
    is_vulnerable, vuln_type = detector.is_address_vulnerable(address)
    
    if is_vulnerable:
        console.print(f"[red]✗ Address is vulnerable![/red]")
        console.print(f"[yellow]Vulnerability type: {vuln_type}[/yellow]")
    else:
        console.print(f"[green]✓ Address appears safe[/green]")
    
    # Show additional info
    if detector._is_p2pkh_address(address):
        console.print("[cyan]Address type: P2PKH (Pay to Public Key Hash)[/cyan]")
    else:
        console.print("[cyan]Address type: Not P2PKH[/cyan]")


@cli.command()
def test_detection():
    """Test quantum emergency detection with sample data"""
    from datetime import datetime, timedelta
    from src.services.quantum_detector import QuantumEmergencyDetector, WalletActivity
    
    console.print("[yellow]Testing quantum emergency detection...[/yellow]")
    
    detector = QuantumEmergencyDetector()
    
    # Create sample dormant wallet activities
    now = datetime.utcnow()
    activities = []
    
    # Simulate 6 dormant wallets becoming active within 30 minutes
    for i in range(6):
        activity = WalletActivity(
            address=f"1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf{i}a",
            transaction_time=now - timedelta(minutes=i*5),
            amount=50 * 100_000_000,  # 50 BTC
            balance=50 * 100_000_000,
            dormancy_days=3650 + i*365,  # 10-15 years dormant
            last_activity_before=now - timedelta(days=3650 + i*365),
            vulnerability_type="P2PK"
        )
        activities.append(activity)
    
    # Analyze patterns
    patterns = detector.analyze_recent_activity(activities)
    
    if patterns:
        console.print(f"[red]Found {len(patterns)} emergency patterns![/red]")
        
        for pattern in patterns:
            table = Table(title=f"Pattern: {pattern.pattern_type}", show_header=True)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Severity", pattern.severity)
            table.add_row("Confidence", f"{pattern.confidence:.2f}")
            table.add_row("Affected Wallets", str(len(pattern.affected_wallets)))
            table.add_row("Total Value (BTC)", f"{pattern.total_value / 100_000_000:,.2f}")
            
            console.print(table)
    else:
        console.print("[green]No emergency patterns detected[/green]")


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()