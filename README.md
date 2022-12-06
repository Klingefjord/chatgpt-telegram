# ChatGPT Telegram Bot

A telegram bot that uses a headless chrome wrapper to communicate with ChatGPT.

see: https://github.com/Klingefjord/ChatGPT-API-Python

## How to Install

### Step 1: Install Python and Miniconda

1. Go to the [Miniconda download page](https://docs.conda.io/en/latest/miniconda.html).
2. Click on the appropriate installer for your operating system.
3. Follow the prompts to complete the installation.

### Step 2: Create a conda environment

1. Open a terminal or command prompt.
2. Navigate to the directory where you want to create the environment.
3. Run `conda env create -f environment.yml` to create the environment.
4. Activate the newly created environment `conda activate chat`

### Step 3: Install Playwright

1. Open a terminal or command prompt.
2. Navigate to the directory where you installed Miniconda.
3. Run `playwright install` to download the necessary Chromium software.
4. Run `playwright install-deps` to download the necessary dependencies

### Step 4: Set up your Telegram bot

1. Set up your Telegram bot token and user ID in the `.env` file. See [these instructions](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) for more information on how to do this.
2. Edit the `.env.example` file, rename it to `.env`, and place your values in the appropriate fields.

## To run:

`python main.py`

## Credits

- Based on [@Altryne](https://twitter.com/altryne/status/1598902799625961472) on Twitter (https://github.com/altryne/chatGPT-telegram-bot)
