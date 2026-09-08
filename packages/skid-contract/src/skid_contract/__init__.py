"""The route declaration both sides of the socket derive from.

Imported by `skid.routes` on the service side and by `skid_mcp.client` on the
client side, so a tool cannot exist on one side only. It depends on nothing,
which is what lets each side install it without acquiring the other's weight.
"""
