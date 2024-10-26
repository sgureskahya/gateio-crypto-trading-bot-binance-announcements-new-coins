import ast
import json
import os.path
import random
import re
import string
import time

import requests
from gate_api import ApiClient
from gate_api import SpotApi

import gateio_new_coins_announcements_bot.globals as globals
from gateio_new_coins_announcements_bot.auth.gateio_auth import load_gateio_creds
from gateio_new_coins_announcements_bot.load_config import load_config
from gateio_new_coins_announcements_bot.logger import logger
from gateio_new_coins_announcements_bot.store_order import load_order

config = load_config("config.yml")
client = load_gateio_creds("auth/auth.yml")
spot_api = SpotApi(ApiClient(client))

supported_currencies = None

previously_found_coins = set()

def get_upbit_announcement():
  """
  Upbit borsasından yeni coin listeleme duyurularını çeker.
  """
  url = "https://api.upbit.com/v1/market/all"  # Upbit API'sinden tüm marketleri çekmek için örnek bir uç nokta
  try:
      response = requests.get(url)
      response.raise_for_status()
      markets = response.json()
      # Burada yeni coin listelemelerini kontrol etmek için gerekli işlemleri yapabilirsiniz
      # Örneğin, yeni eklenen marketleri tespit edebilirsiniz
      logger.info("Upbit market bilgileri başarıyla çekildi.")
      return markets
  except requests.exceptions.RequestException as e:
      logger.error(f"Upbit API isteği başarısız: {e}")
      return None

def get_last_coin():
  """
  Returns new Symbol when appropriate
  """
  # scan Upbit Announcement
  upbit_announcements = get_upbit_announcement()
  found_coin = None

  if upbit_announcements:
      # Örnek olarak, yeni eklenen marketleri kontrol edebiliriz
      for market in upbit_announcements:
          market_id = market['market']
          if market_id not in previously_found_coins:
              found_coin = market_id
              previously_found_coins.add(market_id)
              logger.info("New Upbit coin detected: " + market_id)
              break

  return found_coin

def store_new_listing(listing):
  """
  Only store a new listing if different from existing value
  """
  if listing and not listing == globals.latest_listing:
      logger.info("New listing detected")
      globals.latest_listing = listing
      globals.buy_ready.set()

def search_and_update():
  """
  Pretty much our main func
  """
  while not globals.stop_threads:
      sleep_time = 3
      for x in range(sleep_time):
          time.sleep(1)
          if globals.stop_threads:
              break
      try:
          latest_coin = get_last_coin()
          if latest_coin:
              store_new_listing(latest_coin)
          elif globals.test_mode and os.path.isfile("test_new_listing.json"):
              store_new_listing(load_order("test_new_listing.json"))
              if os.path.isfile("test_new_listing.json.used"):
                  os.remove("test_new_listing.json.used")
              os.rename("test_new_listing.json", "test_new_listing.json.used")
          logger.info(f"Checking for coin announcements every {str(sleep_time)} seconds (in a separate thread)")
      except Exception as e:
          logger.info(e)
  else:
      logger.info("while loop in search_and_update() has stopped.")

def get_all_currencies(single=False):
  """
  Get a list of all currencies supported on gate io
  :return:
  """
  global supported_currencies
  while not globals.stop_threads:
      logger.info("Getting the list of supported currencies from gate io")
      all_currencies = ast.literal_eval(str(spot_api.list_currencies()))
      currency_list = [currency["currency"] for currency in all_currencies]
      with open("currencies.json", "w") as f:
          json.dump(currency_list, f, indent=4)
          logger.info(
              "List of gate io currencies saved to currencies.json. Waiting 5 " "minutes before refreshing list..."
          )
      supported_currencies = currency_list
      if single:
          return supported_currencies
      else:
          for x in range(300):
              time.sleep(1)
              if globals.stop_threads:
                  break
  else:
      logger.info("while loop in get_all_currencies() has stopped.")

def load_old_coins():
  if os.path.isfile("old_coins.json"):
      with open("old_coins.json") as json_file:
          data = json.load(json_file)
          logger.debug("Loaded old_coins from file")
          return data
  else:
      return []

def store_old_coins(old_coin_list):
  with open("old_coins.json", "w") as f:
      json.dump(old_coin_list, f, indent=2)
      logger.debug("Wrote old_coins to file")
