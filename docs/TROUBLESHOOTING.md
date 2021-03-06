Troubleshooting
===============

The skill is installed, but erroring when invoked
-------------------------------------------------

If everything is installed and the connectivity working, but your Echo is saying "there was a problem with your skill" or similary, try checking the [Cloudwatch logs](https://console.aws.amazon.com/cloudwatch/) (note there's a delay in getting the latest logs).
The squeeze-alexa logs are designed to be quite readable, and should help track down the problem.

If you think it's the speech, try using the test input page on the Amazon dev account portal.

If all else fails, raise an issue here...

Debugging SSL / certificate problems directly
---------------------------------------------

For `$MY_HOSTNAME` and `$MY_PORT` you can substitute your home IP / domain name (as used above). It also assumes your client cert is called `squeeze-alexa.pem`:

```bash
openssl s_client -connect $MY_HOSTNAME:$MY_PORT -cert squeeze-alexa.pem | openssl x509
```
Type <kbd>Ctrl</kbd><kbd>d</kbd> to exit.
If successful, this should give you a PEM-style certificate block with some info about your cert).

For more debugging:
```bash
openssl s_client -connect $MY_HOSTNAME:$MY_PORT -quiet -cert squeeze-alexa.pem
```
Type `status`, and if a successful end-to-end connection is made you should see some gibberish that looks a bit like:
`...status   player_name%3AUpstairs...player_connected%3A1 player_ip%3A192.168.1...`

Checking your LMS CLI is actually working
-----------------------------------------

Assuming your LMS IP restrictions allow it (check the LMS GUI security settings), and that you are using the standard 9090 CLI port, you can normally telnet:

```bash
    telnet $LMS 9090
```
where `LMS` is the address of your Squeezebox server - usually this will be the same as `$MY_HOSTNAME` (though you might use the local name).
Then type `status`, or some other command, and see if you get an encoded response. If not, you **need** to fix this first.

You can also try it directly on the LMS box if you think there's some networking problem. Use `netcat` (e.g. `ipkg install netcat`) if you have it:

```bash
    echo "status" | netcat $MY-SERVER 9090
```

(and try `localhost` if that's not working. If still no joy, your DNS setup might be confused).

### Resilience / performance testing the SSL connection
For the hardcore amongst you, you can check performance (and that there are no TLS bugs / obvious holes):

```bash
openssl s_time -bugs -connect $MY_HOSTNAME:$MY_PORT -cert squeeze-alexa.pem -verify 4
```
