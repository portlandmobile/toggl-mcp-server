#!/usr/bin/env python3
"""
Simple Toggl Time Tracking MCP Server - Track your time with Toggl
"""
import os
import sys
import logging
import json
import base64
from datetime import datetime, timezone
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("toggl-server")

# Initialize MCP server - NO PROMPT PARAMETER!
mcp = FastMCP("toggl")

# Configuration
API_TOKEN = os.environ.get("TOGGL_API_TOKEN", "")
BASE_URL = "https://api.track.toggl.com/api/v9"

# Debug: Log token status at startup
logger.info(f"API Token configured: {'Yes' if API_TOKEN else 'No'}")
if API_TOKEN:
    logger.info(f"API Token length: {len(API_TOKEN)}")
    logger.info(f"API Token starts with: {API_TOKEN[:8]}...")
else:
    logger.warning("TOGGL_API_TOKEN environment variable not found")

# === UTILITY FUNCTIONS ===

def get_auth_header():
    """Create basic auth header for Toggl API."""
    if not API_TOKEN:
        return {}
    
    # Toggl uses API token as username with 'api_token' as password
    credentials = f"{API_TOKEN}:api_token"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}

def format_duration(seconds):
    """Format duration in seconds to human readable format."""
    if seconds < 0:
        return "Running..."
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def format_time_entry(entry):
    """Format a time entry for display."""
    description = entry.get('description', 'No description')
    duration = entry.get('duration', 0)
    start = entry.get('start', '')
    
    # Parse start time
    start_time = ""
    if start:
        try:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            start_time = dt.strftime('%Y-%m-%d %H:%M')
        except:
            start_time = start
    
    return f"• {description} - {format_duration(duration)} (started: {start_time})"

async def get_workspace_id():
    """Get the default workspace ID for the user."""
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Content-Type": "application/json", **get_auth_header()}
            response = await client.get(f"{BASE_URL}/me", headers=headers, timeout=10)
            response.raise_for_status()
            user_data = response.json()
            
            # Log the response for debugging
            logger.info(f"User data response: {user_data}")
            
            workspace_id = user_data.get('default_workspace_id')
            if not workspace_id:
                logger.warning(f"No default_workspace_id found in response. Available keys: {list(user_data.keys())}")
                # Try to get the first workspace if no default is set
                workspaces = user_data.get('workspaces', [])
                if workspaces:
                    workspace_id = workspaces[0].get('id')
                    logger.info(f"Using first available workspace: {workspace_id}")
            
            return workspace_id
        except Exception as e:
            logger.error(f"Failed to get workspace ID: {e}")
            return None

# === MCP TOOLS ===

@mcp.tool()
async def start_timer(description: str = "", project_id: str = "") -> str:
    """Start a new timer with optional description and project ID."""
    logger.info(f"Starting timer: {description}")
    
    if not API_TOKEN:
        return "❌ Error: TOGGL_API_TOKEN not configured"
    
    if not description.strip():
        return "❌ Error: Description is required to start a timer"
    
    try:
        workspace_id = await get_workspace_id()
        if not workspace_id:
            return "❌ Error: Could not retrieve workspace ID. Please check your Toggl API token and account permissions. Use the debug_workspace tool to investigate further."
        
        # Prepare the time entry data
        entry_data = {
            "description": description.strip(),
            "start": datetime.now(timezone.utc).isoformat(),
            "duration": -1,  # -1 indicates a running timer
            "created_with": "toggl-mcp-server",
            "wid": workspace_id  # Add workspace ID to request body
        }
        
        # Add project ID if provided
        if project_id.strip():
            try:
                entry_data["project_id"] = int(project_id.strip())
            except ValueError:
                return f"❌ Error: Invalid project ID: {project_id}"
        
        async with httpx.AsyncClient() as client:
            headers = {"Content-Type": "application/json", **get_auth_header()}
            response = await client.post(
                f"{BASE_URL}/time_entries",
                json=entry_data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            timer_id = data.get('id')
            return f"✅ Timer started: '{description}' (ID: {timer_id})"
            
    except httpx.HTTPStatusError as e:
        return f"❌ API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error starting timer: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def stop_timer() -> str:
    """Stop the currently running timer."""
    logger.info("Stopping current timer")
    
    if not API_TOKEN:
        return "❌ Error: TOGGL_API_TOKEN not configured"
    
    try:
        # First, get the current running timer
        async with httpx.AsyncClient() as client:
            headers = {"Content-Type": "application/json", **get_auth_header()}
            response = await client.get(
                f"{BASE_URL}/me/time_entries/current",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            current_entry = response.json()
            
            if not current_entry:
                return "❌ No timer is currently running"
            
            workspace_id = current_entry.get('workspace_id')
            entry_id = current_entry.get('id')
            description = current_entry.get('description', 'No description')
            start_time = current_entry.get('start')
            
            if not workspace_id or not entry_id:
                return "❌ Error: Could not get timer details"
            
            # Stop the timer by setting the stop time
            stop_data = {
                "stop": datetime.now(timezone.utc).isoformat()
            }
            
            response = await client.put(
                f"{BASE_URL}/time_entries/{entry_id}",
                json=stop_data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Calculate duration
            duration = data.get('duration', 0)
            duration_str = format_duration(duration)
            
            return f"✅ Timer stopped: '{description}' - Duration: {duration_str}"
            
    except httpx.HTTPStatusError as e:
        return f"❌ API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error stopping timer: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def debug_workspace() -> str:
    """Debug tool to check workspace ID retrieval and API connectivity."""
    logger.info("Debugging workspace ID retrieval")
    
    if not API_TOKEN:
        return "❌ Error: TOGGL_API_TOKEN not configured"
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {"Content-Type": "application/json", **get_auth_header()}
            
            # Test the /me endpoint
            response = await client.get(f"{BASE_URL}/me", headers=headers, timeout=10)
            response.raise_for_status()
            user_data = response.json()
            
            debug_info = "🔍 Debug Information:\n\n"
            debug_info += f"✅ API Connection: Success\n"
            debug_info += f"📊 Response Status: {response.status_code}\n"
            debug_info += f"🔑 API Token Present: {'Yes' if API_TOKEN else 'No'}\n"
            debug_info += f"🔑 Token Length: {len(API_TOKEN) if API_TOKEN else 0}\n"
            debug_info += f"🔑 Token Preview: {API_TOKEN[:8] + '...' if API_TOKEN else 'N/A'}\n"
            debug_info += f"🌐 Base URL: {BASE_URL}\n\n"
            
            debug_info += "📋 User Data Response:\n"
            debug_info += f"• Full Name: {user_data.get('fullname', 'N/A')}\n"
            debug_info += f"• Email: {user_data.get('email', 'N/A')}\n"
            debug_info += f"• Default Workspace ID: {user_data.get('default_workspace_id', 'N/A')}\n"
            debug_info += f"• Workspaces: {len(user_data.get('workspaces', []))} found\n\n"
            
            # Show all workspaces
            workspaces = user_data.get('workspaces', [])
            if workspaces:
                debug_info += "🏢 Available Workspaces:\n"
                for ws in workspaces:
                    debug_info += f"• ID: {ws.get('id')} - Name: {ws.get('name', 'N/A')}\n"
            else:
                debug_info += "⚠️ No workspaces found in response\n"
            
            # Test workspace ID retrieval function
            workspace_id = await get_workspace_id()
            debug_info += f"\n🔧 get_workspace_id() result: {workspace_id}\n"
            
            return debug_info
            
    except httpx.HTTPStatusError as e:
        return f"❌ API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error in debug_workspace: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def view_timer_stats(days: str = "7") -> str:
    """View timer statistics for the specified number of days (default: 7 days)."""
    logger.info(f"Viewing timer stats for {days} days")
    
    if not API_TOKEN:
        return "❌ Error: TOGGL_API_TOKEN not configured"
    
    try:
        # Convert days to integer
        try:
            days_int = int(days) if days.strip() else 7
            if days_int <= 0:
                days_int = 7
        except ValueError:
            days_int = 7
        
        # Get current running timer
        current_timer = None
        async with httpx.AsyncClient() as client:
            headers = {"Content-Type": "application/json", **get_auth_header()}
            
            # Check for current timer
            response = await client.get(
                f"{BASE_URL}/me/time_entries/current",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            current_timer = response.json()
            
            # Get recent time entries
            since_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            since_date = since_date.replace(day=since_date.day - days_int + 1)
            
            params = {
                "since": since_date.isoformat(),
            }
            
            response = await client.get(
                f"{BASE_URL}/me/time_entries",
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            entries = response.json()
            
            # Build stats
            stats_text = f"📊 Timer Stats (Last {days_int} days):\n\n"
            
            # Current timer status
            if current_timer:
                desc = current_timer.get('description', 'No description')
                start = current_timer.get('start', '')
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    elapsed = datetime.now(timezone.utc) - start_dt
                    elapsed_str = format_duration(int(elapsed.total_seconds()))
                    stats_text += f"⏱️ Currently Running: '{desc}' - {elapsed_str}\n\n"
                except:
                    stats_text += f"⏱️ Currently Running: '{desc}'\n\n"
            else:
                stats_text += "⏸️ No timer currently running\n\n"
            
            if not entries:
                stats_text += "No time entries found for the selected period."
                return stats_text
            
            # Calculate total time
            total_seconds = 0
            completed_entries = []
            
            for entry in entries:
                duration = entry.get('duration', 0)
                if duration > 0:  # Only count completed entries
                    total_seconds += duration
                    completed_entries.append(entry)
            
            stats_text += f"⏰ Total Time Tracked: {format_duration(total_seconds)}\n"
            stats_text += f"📈 Number of Entries: {len(completed_entries)}\n"
            
            if completed_entries:
                avg_duration = total_seconds / len(completed_entries)
                stats_text += f"📊 Average Entry Duration: {format_duration(int(avg_duration))}\n\n"
                
                # Show recent entries (up to 10)
                stats_text += "Recent Entries:\n"
                recent_entries = sorted(completed_entries, key=lambda x: x.get('start', ''), reverse=True)[:10]
                
                for entry in recent_entries:
                    stats_text += format_time_entry(entry) + "\n"
            
            return stats_text
            
    except httpx.HTTPStatusError as e:
        return f"❌ API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting timer stats: {e}")
        return f"❌ Error: {str(e)}"

# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting Toggl Time Tracking MCP server...")
    
    if not API_TOKEN:
        logger.warning("TOGGL_API_TOKEN not set - server will not be able to connect to Toggl API")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)