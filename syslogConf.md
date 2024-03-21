# Configuring Syslog Server for Correct CEF Log Formatting

## Overview

This guide outlines how to configure your syslog server to handle CEF logs properly, addressing common causes of formatting issues.

## Causes of Incorrect CEF Log Formatting

CEF logs can be formatted incorrectly due to the syslog server's default behavior, which includes appending the application name and a colon at the start of each log message. Additionally, the priority level of the log is included, leading to an extra space being prepended to each log entry. This default formatting behavior can disrupt the integrity of CEF logs, making them difficult to parse and analyze accurately.

## Custom Configuration for Correct CEF Log Formatting

To bypass the syslog server's default functionality and ensure CEF logs are stored in the correct format, a custom configuration is required. This configuration will direct CEF logs to a separate file, dedicated solely to CEF logs, ensuring they are not mixed with other log types and are easy to analyze.

We have tested this configuration on our testing syslog server to ensure its effectiveness. Below is the necessary configuration:

```plaintext
# /etc/rsyslog.d/cef-logs.conf

# Define a template for CEF logs
$template RawCEFLogFormat,"CEF:%msg%\n"

# Filter and store CEF logs that contain "0|Cloudflare|TrafficLogs", then stop processing
:msg, contains, "0|Cloudflare|TrafficLogs" /var/log/cef;RawCEFLogFormat
& stop
```

### Steps to Apply the Configuration

1. **Create a Configuration File**: Save the above configuration in `/etc/rsyslog.d/cef-logs.conf`. This keeps custom configurations separate from the default `rsyslog` settings.

2. **Restart Syslog Service**: Apply the new configuration by restarting the `rsyslog` service:
   ```bash
   sudo systemctl restart rsyslog
   ```

3. **Verify Log Output**: Ensure that CEF logs are being correctly formatted and stored in `/var/log/cef`. You can use `tail` or other command-line tools to inspect the logs:
   ```bash
   tail -f /var/log/cef
   ```

## Sources

The configuration and best practices outlined in this guide are based on our extensive testing and the following sources:

- [Discussion on the issue we are facing](https://community.microfocus.com/cyberres/arcsight/f/discussions/344328/websense-cef-syslog-events-not-properly-parsed)
- [Another Thread on a similar issue](https://github.com/rsyslog/rsyslog/issues/4309)

By following this guide, you can configure your syslog server to properly format and store CEF logs.