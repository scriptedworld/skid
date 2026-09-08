"""The client side of the socket: the MCP server and the command line client.

Neither reaches the model, the queue or the config. Both speak plain HTTP to the
socket systemd hands the service, so this package installs with httpx and mcp
and nothing else.
"""
