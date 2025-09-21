# Toggl Time Tracking MCP Server

A Model Context Protocol (MCP) server that provides time tracking functionality through the Toggl API.

## Purpose

This MCP server provides a secure interface for AI assistants to manage time tracking with Toggl, allowing you to start timers, stop timers, and view time tracking statistics directly from Claude Desktop.

## Features

### Current Implementation

- **`start_timer`** - Start a new timer with description and optional project ID
- **`stop_timer`** - Stop the currently running timer
- **`view_timer_stats`** - View time tracking statistics for a specified number of days

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- Toggl Track account with API token
- Active internet connection

## Installation

See the step-by-step instructions provided with the files.

## Usage Examples

In Claude Desktop, you can ask:

- "Start a timer for working on the project documentation"
- "Stop my current timer"
- "Show me my time tracking stats for the last 7 days"
- "Start a timer for meeting with client and use project ID 123456"
- "What are my timer statistics for the past 30 days?"

## Getting Your Toggl API Token

1. Log in to your Toggl Track account
2. Go to Profile Settings (click your avatar in the top right)
3. Scroll down to the "API Token" section
4. Copy your API token
5. Use this token when setting up the Docker secret

## Architecture

```
Claude Desktop → MCP Gateway → Toggl MCP Server → Toggl API
                      ↓
             Docker Desktop Secrets
             (TOGGL_API_TOKEN)
```

## Development

### Local Testing

```bash
# Set environment variables for testing
export TOGGL_API_TOKEN="your-toggl-api-token"

# Run directly
python toggl_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python toggl_server.py
```

### Adding New Tools

1. Add the function to `toggl_server.py`
2. Decorate with `@mcp.tool()`
3. Update the catalog entry with the new tool name
4. Rebuild the Docker image

## API Endpoints Used

- `GET /api/v9/me` - Get user information and default workspace
- `GET /api/v9/me/time_entries/current` - Get currently running timer
- `POST /api/v9/workspaces/{workspace_id}/time_entries` - Create new timer
- `PUT /api/v9/workspaces/{workspace_id}/time_entries/{entry_id}` - Update/stop timer
- `GET /api/v9/me/time_entries` - Get time entry history

## Troubleshooting

### Tools Not Appearing

- Verify Docker image built successfully
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

### Authentication Errors

- Verify secrets with `docker mcp secret list`
- Ensure your Toggl API token is correct
- Check that TOGGL_API_TOKEN secret name matches in code and catalog

### Timer Issues

- Ensure you have a valid Toggl Track account
- Verify your API token has proper permissions
- Check that you're using the correct workspace

## Security Considerations

- All secrets stored in Docker Desktop secrets
- API token never hardcoded or logged
- Running as non-root user
- Secure HTTPS communication with Toggl API

## License

MIT License