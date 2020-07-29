#!/usr/bin/env python3

import logging
from collections import OrderedDict
from hashlib import sha1

import requests
from bs4 import BeautifulSoup

import helpers

import os
import re
import urllib
from urllib.request import urlretrieve
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TweetToot:

    app_name = ""
    twitter_url = ""
    mastodon_url = ""
    mastodon_token = ""

    def __init__(
        self, app_name: str, twitter_url: str, mastodon_url: str, mastodon_token: str
    ):

        self.app_name = app_name
        self.twitter_url = twitter_url
        self.mastodon_url = mastodon_url
        self.mastodon_token = mastodon_token

    def relay(self):

        """ Main code which relays tweets to the Mastodon instance.

        :type self:
        :param self:
    
        :raises:
    
        :rtype: bool
        """

        if not self.app_name:

            logger.error(f"relay() => Application name in config is incorrect/empty.")

            return False

        if not self.twitter_url:

            logger.error(f"relay() => Twitter URL in config is incorrect/empty.")

            return False

        if not self.mastodon_url:

            logger.error(f"relay() => Mastodon URL in config is incorrect/empty.")

            return False

        if not self.mastodon_token:

            logger.error(f"relay() => Mastodon token in config is incorrect/empty.")

            return False

        logger.info(
            f"relay() => Init relay from {self.twitter_url} to {self.mastodon_url}. State file {self._get_timestamp_file_path()}"
        )

        tweets = self._get_tweets()

        if not tweets:

            return True

        logger.debug(f"relay() => {str(tweets)}")

        last_timestamp = 0

        for tweet_time, tweet in tweets.items():

            logger.info(f"relay() => Tweeting {tweet['id']} to {self.mastodon_url}")

            last_timestamp = (
                tweet_time if tweet_time > last_timestamp else last_timestamp
            )

            if tweet["img"] != "null":
                img_u = tweet["img"]
                tweet_id = tweet["id"]
                d_path = helpers._config("TT_CACHE_PATH")+ "img_"+tweet_id
                urllib.request.urlretrieve(img_u, d_path)

                headers = {}
                headers["Authorization"] = f"Bearer {self.mastodon_token}"
                file = {'file': open(d_path, 'rb')}

                m_response = requests.post(
                    url=f"{self.mastodon_url}/api/v1/media", files=file, headers=headers
                )
                if m_response.status_code == 200:

                    logger.info(
                        f"toot_the_tweet() => OK. Tooted {tweet_id}'s media' to {self.mastodon_url}."
                    )
                    logger.debug(f"toot_the_tweet() => Response: {m_response.text}")
                    m_id = m_response.json()["id"]
                else:

                    logger.error(
                        f"toot_the_tweet() => Could not toot {tweet_id}'s media' to {self.mastodon_url}."
                    )
                    logger.error(f"toot_the_tweet() => Response: {m_response.text}")
                    m_id = "null"
                self._toot_the_tweet(
                    mastodon_url=self.mastodon_url,
                    tweet_id=tweet["id"],
                    tweet_body=tweet["text"],
                    tweet_time=tweet_time,
                    media_id=m_id
                )
                os.remove(d_path)
            else:
                self._toot_the_tweet(
                mastodon_url=self.mastodon_url,
                tweet_id=tweet["id"],
                tweet_body=tweet["text"],
                tweet_time=tweet_time,
                media_id="null"
            )

        self._set_last_timestamp(timestamp=last_timestamp)

    def _get_tweets(self):

        """ Get list of new tweets, with tweet ID and content, from configured Twitter account URL.
        This function relies on BeautifulSoup to extract the tweet IDs and content of all tweets on the specified page.
        The data is returned as a list of dictionaries that can be used by other functions.

        :type self:
        :param self:

        :raises:

        :rtype: dict
        """

        tweets = OrderedDict()
        last_timestamp = self._get_last_timestamp()

        headers = {}
        headers["accept-language"] = "en-US,en;q=0.9"
        headers["dnt"] = "1"
        headers["user-agent"] = self.app_name

        data = requests.get(self.twitter_url)
        html = BeautifulSoup(data.text, "html.parser")
        timeline = html.select("div.tweet-text")
        tweet_body = html.select("table.tweet")
        count = 0

        if timeline is None:

            logger.error(
                f"get_tweets() => Could not retrieve tweets from the page. Please make sure the source Twitter URL ({self.twitter_url}) is correct."
            )
            return False

        logger.info(
            f"get_tweets() => Fetched {len(timeline)} tweets for {self.twitter_url}."
        )

        for tweet in timeline:

            try:

                tweet_time = int(tweet.attrs["data-id"])

                if tweet_time > last_timestamp:

                    tweet_id = tweet.attrs["data-id"]
                    tweet_text = tweet.select("div > div")[0].get_text()

                    # fix urls in links
                    a_tags = tweet.select("a.twitter_external_link")
                    tweet_img = "null"
                    if len(a_tags) > 0:
                        for at in a_tags:
                            url = f'{at["data-url"]} '
                            at = at.get_text()
                            tweet_text = str(tweet_text).replace(str(at), url)
                            ori = url
                            if "https://twitter.com/"  in ori and "/photo/" in ori:
                                url = ori
                                url = url.replace("twitter.com","mobile.twitter.com")
                                pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
                                url = re.findall(pattern,url)
                                url = url[0]
                                img_src = requests.get(url)
                                img_html = BeautifulSoup(img_src.text, "html.parser")
                                img = img_html.select("div.media")
                                img = str(img)
                                img_url = re.findall(pattern,img)
                                tweet_img = img_url[0]
                                tweet_text = str(tweet_text).replace(str(ori), "")
                                if "support.twitter.com" in tweet_img:
                                    tweet_img = "null"
                                    tweet_text = tweet_text + ori + "\n This media is marked as sensitive, follow the link above to view."
                            if "https://twitter.com/"  in ori and "/video/" in ori:
                                url = ori
                                url = url.replace("twitter.com","mobile.twitter.com")
                                pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
                                url = re.findall(pattern,url)
                                url = url[0]
                                img_src = requests.get(url)
                                img_html = BeautifulSoup(img_src.text, "html.parser")
                                img = img_html.select("div.media")
                                img = str(img)
                                img_url = re.findall(pattern,img)
                                tweet_img = img_url[0]
                                tweet_text = str(tweet_text).replace(str(ori), "")
                                if "support.twitter.com" in tweet_img:
                                    tweet_img = "null"
                                    tweet_text = tweet_text + ori + "\n This media is marked as sensitive, follow the link above to view."
                            if "https://twitter.com/"  in ori and "/status/" in ori:
                                if "/video/" in ori:
                                    print("")
                                else:
                                    if "/photo/" in ori:
                                        print("")
                                    else:
                                        url = ori
                                        url = url.replace("twitter.com","mobile.twitter.com")
                                        pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
                                        url = re.findall(pattern,url)
                                        url = url[0]
                                        ori_tweet = requests.get(url)
                                        ori_html = BeautifulSoup(ori_tweet.text, "html.parser")
                                        ori_post = ori_html.select("div.tweet-text")[0]
                                        ori_auth = ori_html.select("div.fullname")[0]
                                        ori_post = str(ori_post.get_text())
                                        ori_auth = str(ori_auth.get_text())
                                        ori_post = ori_post.replace("\n", "")
                                        ori_auth = ori_auth.replace("\n", "")
                                        tweet_text = "Retweeted and replied to " + ori_auth + "'s tweet\n(" + ori_post + ")\nAbove is original post\n" + tweet_text
                                        tweet_text = str(tweet_text).replace(str(ori), "")

                    if tweet_body[count].select("span.context"):
                        tweet_context = tweet_body[count].select("span.context")[0]
                        tweet_context = tweet_context.get_text()
                        ori_author = tweet_body[count].select("strong.fullname")[0]
                        ori_author = str(ori_author.get_text())
                        tweet_text = "Retweeted " + ori_author + "'s tweet: \n" + tweet_text
                    if tweet_body[count].select("div.tweet-reply-context"):
                        re_context = tweet_body[count].select("div.tweet-reply-context")[0]
                        re_context = str(re_context.get_text())
                        re_context = re_context.replace("\n", "")
                        if ori:
                            url = ori
                            url = url.replace("twitter.com","mobile.twitter.com")
                            pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
                            url = re.findall(pattern,url)
                            url = url[0]
                            ori_tweet = requests.get(url)
                            ori_html = BeautifulSoup(ori_tweet.text, "html.parser")
                            ori_post = ori_html.select("div.tweet-text")[0]
                            ori_auth = ori_html.select("div.fullname")[0]
                            ori_post = str(ori_post.get_text())
                            ori_auth = str(ori_auth.get_text())
                            ori_post = ori_post.replace("\n", "")
                            ori_auth = ori_auth.replace("\n", "")
                            tweet_text = str(tweet_text).replace(str(ori), "")
                            tweet_text = re_context + "\n(" + ori_post + ")\nAbove is original post\n"  + tweet_text
                        else:
                            tweet_text = re_context + "\n" + tweet_text
                    ori = None

                    count += 1
                    if helpers._config("TT_MODE") == "many-to-one" or helpers._config("TT_MODE") == "many-to-many":
                        author = html.select("table.profile-details")[0].select("div.fullname")[0]
                        user = str(author.get_text())
                        user = user.replace("\n", "")
                        tweet_text = user + ' said: \n' + tweet_text
                    tweets[tweet_time] = {"id": tweet_id, "text": tweet_text, "img": tweet_img}


            except Exception as e:

                logger.error("get_tweets() => An error occurred.")
                logger.error(e)

                continue

        return (
            {k: tweets[k] for k in sorted(tweets, reverse=True)}
            if len(tweets) > 0
            else None
        )

    def _get_last_timestamp(self):

        """ Get the last tweet's timestamp.

        :type self:
        :param self:

        :raises:

        :rtype: int
        """

        ts = helpers._read_file(self._get_timestamp_file_path())

        return int(ts) if ts else 0

    def _set_last_timestamp(self, timestamp: int):

        """ Set the last tweet's timestamp.

        :type self:
        :param self:

        :type timestamp:int:
        :param timestamp:int: Timestamp of current tweet.

        :raises:

        :rtype: bool
        """

        return helpers._write_file(self._get_timestamp_file_path(), str(timestamp))

    def _get_timestamp_file_path(self):

        """ Get file path that stores tweet timestamp.

        :type self:
        :param self:

        :raises:

        :rtype: str
        """

        return (
            helpers._config("TT_CACHE_PATH")
            + "tt_"
            + sha1(
                self.twitter_url.encode("utf-8") + self.mastodon_url.encode("utf-8")
            ).hexdigest()
        )

    def _toot_the_tweet(
        self, mastodon_url: str, tweet_id: str, tweet_body: str, tweet_time: int, media_id: str
    ):

        """ Receieve a dictionary containing Tweet ID and text... and TOOT!
        This function relies on the requests library to post the content to your Mastodon account (human or bot).
        A boolean success status is returned.
            
        :type self:
        :param self:
    
        :type tweet_id:str:
        :param tweet_id:str: Tweet ID.
    
        :type tweet_body:str:
        :param tweet_body:str: Tweet text.
    
        :type tweet_time:int:
        :param tweet_time:int: Tweet timestamp.

        :raises:
    
        :rtype: bool
        """
        
        headers = {}
        headers["Authorization"] = f"Bearer {self.mastodon_token}"
        headers["Idempotency-Key"] = tweet_id

        data = {}
        data["status"] = tweet_body
        data["visibility"] = "unlisted"
        if media_id != "null":
            data["media_ids"] = [media_id]

        response = requests.post(
            url=f"{mastodon_url}/api/v1/statuses", json=data, headers=headers
        )

        if response.status_code == 200:

            logger.info(
                f"toot_the_tweet() => OK. Tooted {tweet_id} to {self.mastodon_url}."
            )
            logger.debug(f"toot_the_tweet() => Response: {response.text}")

            return True

        else:

            logger.error(
                f"toot_the_tweet() => Could not toot {tweet_id} to {self.mastodon_url}."
            )
            logger.error(f"toot_the_tweet() => Response: {response.text}")

            return False
