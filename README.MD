# MastodonTagFinder.py

## About

This program connects to the public feed of specified Mastodon-like servers.

It also connects to specified Mastodon user accounts with at least read:follows + read:search rights.

Posts with a tag followed by a user are added to the federated feed of that user's 
instance using the Mastodon search API call. This will cause those posts to appear 
in the user's home feed.

Tag follow list are periodically rechecked so that users can add and remove tags. 

Posts from profiles with the "noindex" flag set, or "#nobot" in the profile
will be skipped by the script to respect the wishes of those users to 
opt out from automated discovery.

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

## How to create an access token

1. In the Mastodon web app, go to: Preferences | Development 
2. Press the "New Application" button.
3. Give a name for the applications - this will not be used for anything but it is needed.
4. Unselect all "Scopes" apart from "read:follows" and "read:search".
5. Press "Submit". 
6. You will be taken back to the "Your applications" page. 
7. Select the Application you just created.
6. Copy the long string next to "Your access token" and put that to the users file

## Author

Copyright 2022 Andrew Baldwin 
(Fediverse: @baldand@mstdn.thndl.com)

[License](LICENSE)