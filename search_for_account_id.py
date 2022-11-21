#!/usr/bin/env python3

# search for Mastodon account and return account IDs for each result
from urllib.request import urlopen
from mastodon import Mastodon
from credentials import access_token, api_base_url, account_id

# account to search
account_to_search = input('Please enter the account to find (eg @axwax@fosstodon.org): ')

# Initialise Mastodon
mastodon = Mastodon(
    access_token = access_token,
    api_base_url = api_base_url
)

# search for the account and print out the list of results
results_list = mastodon.account_search(account_to_search, limit=None, following=False)
for user in results_list:
    print(user['acct'] + ':', user['id'])