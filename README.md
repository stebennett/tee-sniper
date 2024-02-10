# tee-sniper
A bot for booking golf tee-times.

## Env Vars

Set the environment variables for sending SMS via Twilo. Examples in `.env.example`.

## Usage

Display help
````
# go run cmd/tee-sniper/main.go -h
````

Run tee time booker
````
# go run cmd/tee-sniper/main.go -u 1234 -p 1234 -b https://example.com/ -d 7 -t 15:00 -e 17:00 -n xxxxxxxx -f xxxxxxxxxx
````

````
Usage:
  main [OPTIONS]

Application Options:
  -d, --days=       The number of days ahead to look for a tee-slot
  -t, --timestart=  The time after which a tee-time will be selected
  -e, --timeend=    The time before which a tee-time will be selected
  -r, --retries=    The number of times to retry booking (default: 5)
  -x, --dryrun      Run everything, but don't do the booking and assume it succeeds
  -u, --username=   The username to use for booking
  -p, --pin=        The pin associated with the username for booking
  -b, --baseurl=    The host for the booking website
  -f, --fromnumber= The number to send the confirmation SMS from
  -n, --tonumber=   The number to send the confirmation SMS to

Help Options:
  -h, --help        Show this help message
````