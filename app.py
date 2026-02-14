#!/usr/bin/env python3
"""Interactive Kalshi Omni-Nexus Dashboard."""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.text import Text

from config import API_BASE, KALSHI_TRADER_ID, KALSHI_PRIVATE_KEY
from kalshi_client.auth import KalshiAuth
from kalshi_client.client import KalshiClient
from kalshi_client.exceptions import KalshiAPIError


console = Console()


def show_exchange_status(client: KalshiClient):
    status = client.get_exchange_status()
    color = "green" if status.trading_active else "red"
    console.print(Panel(
        f"Exchange Active: [bold {color}]{status.exchange_active}[/]\n"
        f"Trading Active:  [bold {color}]{status.trading_active}[/]",
        title="Exchange Status",
        border_style=color,
    ))


def show_markets(client: KalshiClient):
    console.print("[dim]Fetching markets...[/]")
    markets, cursor = client.get_markets(limit=15, status="open")
    if not markets:
        console.print("[yellow]No open markets found.[/]")
        return

    table = Table(title=f"Open Markets ({len(markets)} shown)", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Ticker", style="cyan", max_width=25, overflow="ellipsis")
    table.add_column("Title", max_width=45, overflow="ellipsis")
    table.add_column("Yes Bid", justify="right", style="green")
    table.add_column("Yes Ask", justify="right", style="red")
    table.add_column("Volume", justify="right")
    table.add_column("Status", justify="center")

    for i, m in enumerate(markets, 1):
        table.add_row(
            str(i),
            m.ticker[:25],
            m.title[:45],
            f"{m.yes_bid:.0%}" if m.yes_bid else "-",
            f"{m.yes_ask:.0%}" if m.yes_ask else "-",
            f"{m.volume:,}",
            m.status,
        )
    console.print(table)

    choice = Prompt.ask(
        "\nEnter market # for details (or press Enter to go back)",
        default="",
    )
    if choice.isdigit() and 1 <= int(choice) <= len(markets):
        show_market_detail(client, markets[int(choice) - 1].ticker)


def show_market_detail(client: KalshiClient, ticker: str):
    market = client.get_market(ticker)
    console.print(Panel(
        f"[bold]{market.title}[/]\n\n"
        f"Ticker:        {market.ticker}\n"
        f"Event:         {market.event_ticker}\n"
        f"Status:        {market.status}\n"
        f"Subtitle:      {market.subtitle or 'N/A'}\n"
        f"Close Time:    {market.close_time or 'N/A'}\n\n"
        f"[green]Yes Bid:[/]  {market.yes_bid:.0%}    [red]Yes Ask:[/]  {market.yes_ask:.0%}\n"
        f"[green]No Bid:[/]   {market.no_bid:.0%}    [red]No Ask:[/]   {market.no_ask:.0%}\n"
        f"Last Price:    {market.last_price:.0%}\n"
        f"Volume:        {market.volume:,}\n"
        f"Open Interest: {market.open_interest:,}",
        title=f"Market: {ticker}",
        border_style="blue",
    ))

    # Orderbook
    try:
        ob = client.get_orderbook(ticker, depth=5)
        if ob.yes_bids or ob.yes_asks:
            ob_table = Table(title="Order Book (Yes)")
            ob_table.add_column("Bid Price", style="green")
            ob_table.add_column("Bid Qty", style="green")
            ob_table.add_column("Ask Price", style="red")
            ob_table.add_column("Ask Qty", style="red")
            max_rows = max(len(ob.yes_bids), len(ob.yes_asks))
            for i in range(max_rows):
                bid_p = f"{ob.yes_bids[i][0]}c" if i < len(ob.yes_bids) else ""
                bid_q = str(ob.yes_bids[i][1]) if i < len(ob.yes_bids) else ""
                ask_p = f"{ob.yes_asks[i][0]}c" if i < len(ob.yes_asks) else ""
                ask_q = str(ob.yes_asks[i][1]) if i < len(ob.yes_asks) else ""
                ob_table.add_row(bid_p, bid_q, ask_p, ask_q)
            console.print(ob_table)
        else:
            console.print("[dim]No orderbook data for this market.[/]")
    except KalshiAPIError:
        console.print("[dim]Could not fetch orderbook.[/]")


def show_events(client: KalshiClient):
    console.print("[dim]Fetching events...[/]")
    events, _ = client.get_events(limit=15, status="open", with_nested_markets=True)
    if not events:
        console.print("[yellow]No open events found.[/]")
        return

    table = Table(title=f"Open Events ({len(events)} shown)", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Event Ticker", style="cyan", max_width=25, overflow="ellipsis")
    table.add_column("Title", max_width=50, overflow="ellipsis")
    table.add_column("Category", style="magenta")
    table.add_column("Markets", justify="right")

    for i, e in enumerate(events, 1):
        mkt_count = len(e.markets) if e.markets else 0
        table.add_row(
            str(i),
            e.event_ticker[:25],
            e.title[:50],
            e.category,
            str(mkt_count),
        )
    console.print(table)

    choice = Prompt.ask(
        "\nEnter event # for details (or press Enter to go back)",
        default="",
    )
    if choice.isdigit() and 1 <= int(choice) <= len(events):
        show_event_detail(client, events[int(choice) - 1].event_ticker)


def show_event_detail(client: KalshiClient, event_ticker: str):
    event = client.get_event(event_ticker, with_nested_markets=True)
    console.print(Panel(
        f"[bold]{event.title}[/]\n\n"
        f"Ticker:   {event.event_ticker}\n"
        f"Category: {event.category}\n"
        f"Status:   {event.status}\n"
        f"Markets:  {len(event.markets) if event.markets else 0}",
        title=f"Event: {event_ticker}",
        border_style="magenta",
    ))

    if event.markets:
        table = Table(title="Event Markets")
        table.add_column("#", justify="right", style="dim", width=3)
        table.add_column("Ticker", style="cyan", max_width=30, overflow="ellipsis")
        table.add_column("Title", max_width=40, overflow="ellipsis")
        table.add_column("Yes Bid", justify="right", style="green")
        table.add_column("Yes Ask", justify="right", style="red")

        for i, m_data in enumerate(event.markets[:20], 1):
            if isinstance(m_data, dict):
                ticker = m_data.get("ticker", "")
                title = m_data.get("title", "")
                yb = m_data.get("yes_bid", 0)
                ya = m_data.get("yes_ask", 0)
                table.add_row(
                    str(i),
                    ticker[:30],
                    title[:40],
                    f"{yb}c" if yb else "-",
                    f"{ya}c" if ya else "-",
                )
        console.print(table)


def show_portfolio(client: KalshiClient):
    try:
        balance = client.get_balance()
    except KalshiAPIError as e:
        if e.status_code == 401:
            console.print(Panel(
                "[yellow]API key returned 401 on portfolio endpoints.\n"
                "Your key may lack portfolio/trading scope.\n"
                "Check your API key permissions on the Kalshi dashboard.[/]",
                title="Portfolio Access Denied",
                border_style="yellow",
            ))
            return
        raise

    console.print(Panel(
        f"[bold green]Balance: ${balance.balance_dollars:.2f}[/]\n"
        f"Payout:  {balance.payout}c",
        title="Account Balance",
        border_style="green",
    ))

    positions, _ = client.get_positions(limit=20)
    if positions:
        table = Table(title=f"Open Positions ({len(positions)})")
        table.add_column("Ticker", style="cyan")
        table.add_column("Exposure", justify="right")
        table.add_column("PnL", justify="right")
        table.add_column("Resting Orders", justify="right")
        for p in positions:
            pnl_color = "green" if p.realized_pnl >= 0 else "red"
            table.add_row(
                p.ticker,
                f"{p.market_exposure}c",
                f"[{pnl_color}]{p.realized_pnl}c[/]",
                str(p.resting_orders_count),
            )
        console.print(table)
    else:
        console.print("[dim]No open positions.[/]")

    fills, _ = client.get_fills(limit=10)
    if fills:
        table = Table(title=f"Recent Fills (last {len(fills)})")
        table.add_column("Ticker", style="cyan")
        table.add_column("Side")
        table.add_column("Action")
        table.add_column("Qty", justify="right")
        table.add_column("Yes Price", justify="right")
        table.add_column("Time")
        for f in fills[:10]:
            table.add_row(
                f.ticker, f.side, f.action, str(f.count),
                f"{f.yes_price}c", f.created_time[:19],
            )
        console.print(table)


def run_test_agents(client: KalshiClient):
    from agents.orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator(client)
    orchestrator.run_all()


def main():
    if not KALSHI_TRADER_ID or not KALSHI_PRIVATE_KEY:
        console.print("[bold red]Set KALSHI_TRADER_ID and KALSHI_PRIVATE_KEY in .env[/]")
        sys.exit(1)

    auth = KalshiAuth(key_id=KALSHI_TRADER_ID, private_key_pem=KALSHI_PRIVATE_KEY)
    client = KalshiClient(base_url=API_BASE, auth=auth)

    console.print(Panel(
        "[bold cyan]Kalshi Omni-Nexus[/]\n"
        f"[dim]API: {API_BASE}[/]\n"
        f"[dim]Key: {KALSHI_TRADER_ID[:8]}...[/]",
        border_style="cyan",
    ))

    while True:
        console.print()
        console.print("[bold]What would you like to do?[/]")
        console.print("  [cyan]1[/] - Exchange Status")
        console.print("  [cyan]2[/] - Browse Markets")
        console.print("  [cyan]3[/] - Browse Events")
        console.print("  [cyan]4[/] - Portfolio & Balance")
        console.print("  [cyan]5[/] - Run Test Agents")
        console.print("  [cyan]q[/] - Quit")

        choice = Prompt.ask("\nChoice", choices=["1", "2", "3", "4", "5", "q"], default="1")

        try:
            if choice == "1":
                show_exchange_status(client)
            elif choice == "2":
                show_markets(client)
            elif choice == "3":
                show_events(client)
            elif choice == "4":
                show_portfolio(client)
            elif choice == "5":
                run_test_agents(client)
            elif choice == "q":
                console.print("[dim]Goodbye![/]")
                break
        except KalshiAPIError as e:
            console.print(f"[red]API Error: {e}[/]")
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/]")
            break


if __name__ == "__main__":
    main()
