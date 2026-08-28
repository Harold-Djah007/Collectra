# Collectra local launchers

Use `./local-bin/start-collectra` for normal development on the laptop or the
same local network.

Use `./local-bin/start-collectra-public` for a temporary cellular-data test. It
starts a Cloudflare Quick Tunnel, publishes a temporary HTTPS hostname, and
then starts the normal Collectra services. Keep that terminal open for the
entire test.

The public launcher requires `cloudflared`. Follow Cloudflare's official
installation instructions:

https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/

After the launcher prints `Public Collectra address`, open that address on the
phone with Wi-Fi disabled. Publish a new application build in Collectra HQ and
install or update it using a QR code generated while the public launcher is
running. The generated profile then uses HTTPS for application downloads,
submissions, heartbeats, and restores.

Quick Tunnel hostnames change when the tunnel is restarted. They are intended
only for testing and presentations. Do not use them as the production address
or submit sensitive company data through a temporary demo environment. A
permanent deployment must use a stable HTTPS hostname and durable hosted data
services.
