# Troubleshooting & FAQ

This page covers common issues encountered when integrating with Business Central OData Web Services and how to resolve them with Odyn.

## Connection & Authentication

### 401 Unauthorized
- **Domain Prefix**: On-premises BC often requires the domain (`DOMAIN\user`). Ensure you use double backslashes in Python strings: `BasicAuth("DOMAIN\\user", "pass")`.
- **Web Service Access Key**: In some BC versions and configurations, you must use the **Web Service Access Key** generated on the User card in BC as the password, rather than the user's standard Windows password.
- **Instance Configuration**: Ensure the Business Central instance is configured to allow NavUserPassword or Windows authentication as appropriate.

### SSL / Certificate Errors
On-premises servers frequently use self-signed certificates.
- **Solution**: Set `verify_ssl=False` in `BCWebServiceClient.create()`.
- **Warning**: Only do this in trusted internal environments. For production, installing the root CA on the machine running Odyn is preferred.

## Entity & Endpoint Issues

### 404 Not Found
- **Service Name**: The `endpoint` name in Odyn must exactly match the **Service Name** published in the "Web Services" page in Business Central. This is case-sensitive.
- **Published Status**: Ensure the "Published" checkbox is ticked for the service in BC.
- **OData V4**: Odyn uses OData V4. Ensure your server is not restricted to V3.

### Field Not Found
- **Select/Filter**: Ensure the field name matches the **OData Name** of the field in the published service. This often differs from the caption or the internal AL name (e.g., "Customer_No" vs "Customer No.").

## Performance & Limits

### "URL Too Long" (414 Request-URI Too Long)
OData filters are passed in the URL. If you build a massive `is_in()` filter with hundreds of values, the URL will eventually exceed the server's limit (usually around 2KB - 8KB).
- **Solution**: Use `client.get_batch()`. This method automatically chunks your values into multiple smaller requests and merges the resulting DataFrames.

### Rate Limiting
If you see **429 Too Many Requests**, you are hitting the server-side OData limits.
- **Solution**: Decrease the `rate_limit` (e.g., to `5.0`) and `max_connections` (e.g., to `2`) in the client configuration to stay within the server's thresholds.
