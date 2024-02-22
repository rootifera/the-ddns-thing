# The DDNS Thing

Had enough of wrangling with those DDNS tools? Finding them a tad fiddly to set up? And when they do decide
to cooperate, is it still a bit hit-or-miss?

Allow me to introduce you to "The-DDNS-Thing."

"The-DDNS-Thing" is as unreliable as any other DDNS tool, if not worse. You might see it making API
calls here and there, experiencing the odd timeout, and failing without so much as a hint as to why. Frankly, I'm as
puzzled as you are.

At the moment it only supports Cloudflare. This is because Cloudflare is the only one I need.

Anyway, give it a whirl and see how it goes!

### Usage:

The usage is fairly simple. When you run the application for the first time, it creates two files:

```
~/.config/the-ddns-thing/dns_records.cfg
~/.config/the-ddns-thing/credentials.cfg
```

You will need to edit both of these files for the application to function.

##### credentials.cfg:

This is where you set the credentials. It's a TOML file with expected values:

```
[credentials]
api_key = PFZcfNy9dZwPNGk-ca76CpKQwMYBPFZcfNy
zone_id = bac2c70a29af0af61ef61e219410ae02902
email = hey@isuckatpython.com
```

No support for a global API key; you will need to create an API Token. I named the config value 'api_key,' and I just
noticed it should have been 'api_token.' If you want to manage multiple domains, unfortunately, this is not possible at
the moment, but it's on my to-do list.

##### dns_records.cfg

As you might have already guessed, this is where you configure the records you want to update dynamically. It's another
TOML file:

```
[app1.whatever.com]
[app2.whatever.com]
[hey.whatever.com]

# following record doesn't exist:
[new-record.whatever.com]
proxied=false # you can set this for new records, existing records won't update.
```

This is the most basic setup you can have, just your A records in brackets. The application will check if these records
exist. If they do, it will compare your IP address against the record and update if necessary. After you run the program
with some records, you will see the config file looking a little different:

```
[app1.whatever.com]
id = ea64db18dd72578a276ea64db18dd725

[app2.whatever.com]
id = 6bdf812964452cb5e316f7a1087aed8e
...
```

The ID comes from Cloudflare's API. This way, instead of getting all records repeatedly, we interact with the records
directly using their ID. New records won't have that during the run they get created. The next time you run the
application, the ID field will be auto-filled.

### TODO:

- Some sort of logging
- Maybe a report HTML file
- Multi domain support
