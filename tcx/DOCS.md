# Documentation

## How to use

1. Add the Github repo to your Hass.io: <https://github.com/jlipton/hassio-addons>
2. Install the addon
3. Configure the options in the addon (see descriptions for each option below).
5. Start the addon
6. Restart Home Assistant Core

**Note**: _If you did not specify a `subdomain` or `hostname` you will need to_
_open the web interface to get your ngrok.io url, or you can use the_
_[API](#home-assistant-integration) to be notified through Home Assistant._

Example add-on configuration:

```yaml
  log_level: info
  JANDY_USERNAME: <username>
  JANDY_PASSWORD: <PASSWORD>
  BROKER: 192.168.14.50
  BROKER_USERNAME: <username>
  BROKER_PASSWORD: <PASSWORD>
```





### Further reading

You can monitor almost anything about the tunnel as long as it is active.
See [ngrok's api documentation][ngrok_docs_api] for details.

[ngrok_docs_tunnels]: https://ngrok.com/docs#tunnel-definitions
[rest_docs]: https://www.home-assistant.io/integrations/rest/
[packages_docs]: https://www.home-assistant.io/docs/configuration/packages/
[ngrok_docs_api]: https://ngrok.com/docs#client-api
[trusted_proxies_docs]: https://www.home-assistant.io/integrations/http#reverse-proxies
