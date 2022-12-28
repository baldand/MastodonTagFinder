# MastodonTagFinder.py

## About

This program connects to the public feed of specified Mastodon-like servers.

It also connects to specified Mastodon user accounts with at least read:follows + read:search rights.

Any posts with a tag followed by a user are added to the federated feed of that user's 
instance using the Mastodon search API call. This will cause those posts to appear 
in the user's home feed.

Tag follow list are periodically rechecked so that users can add and remove tags. 

## Data usage warning

If you connect to a large number of high volume servers,
incoming bandwidth will be quite significant (100s of KB per second or more). This will work best when incoming data is not charged.

CPU usage should be relatively low (few percent on one core) and also memory usage.

## Dependencies
- Python 3.8
- aiohttp

## Usage

```
python3 MastodonTagFinder.py server_list_file user_list_file
```

Two files must be supplied at startup:

- server_list_file. A list of servers, one name per line. An example is included here.
- user_list_file. A list of users in the format "server,access_token" per line.

Note that access tokens must include read:follows + read:search rights

## Author

Copyright 2022 Andrew Baldwin 
(Fediverse: @baldand@mstdn.thndl.com)

[License](LICENSE)