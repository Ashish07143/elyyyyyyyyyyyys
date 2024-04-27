from loguru import logger
import requests
import asyncio

import extra
import model


async def start():
    extra.show_logo()
    extra.show_dev_info()
    extra.show_menu(["Registration new accounts on BonusBlock", "Make actions on Elys (swaps, staking, liquidity)"])

    task = int(input(">> "))

    async def launch_wrapper(index, proxy, private_key, discord_token, twitter_token):
        async with semaphore:
            await account_flow(lock, index+1, proxy, private_key, config, task, discord_token, twitter_token)

    # threads = int(input("\nHow many threads do you want: ").strip())
    threads = 1

    config = extra.read_config()

    proxies = extra.read_txt_file("proxies", "data/proxies.txt")
    mnemonics = extra.read_txt_file("mnemonics", "data/mnemonics.txt")
    discord_tokens = extra.read_txt_file("discord tokens", "data/discord_tokens.txt")
    twitter_tokens = extra.read_txt_file("twitter tokens", "data/twitter_tokens.txt")

    # if config['shuffle_accounts']:
    #     combined = list(zip(indexes, proxies, private_keys))
    #     random.shuffle(combined)
    #     indexes, proxies, private_keys = zip(*combined)

    use_proxy = True
    if len(proxies) == 0:
        if not extra.no_proxies():
            return
        else:
            use_proxy = False

    lock = asyncio.Lock()

    if config['mobile_proxy'].lower() == "yes":
        ip_change_links = extra.read_txt_file("ip change links", "data/ip_change_links.txt")

        mobile_proxy_queue = asyncio.Queue()
        for i in range(len(mnemonics)):
            await mobile_proxy_queue.put(i)

        cycle = []
        for i in range(len(proxies)):
            data_list = (proxies[i], ip_change_links[i], mobile_proxy_queue, config, lock, mnemonics[i], task, discord_tokens[i], twitter_tokens[i])
            cycle.append(data_list)

        tasks = [
            asyncio.create_task(mobile_proxy_wrapper(*data))
            for data in cycle
        ]

        logger.info("Starting...")
        await asyncio.gather(*tasks)

        logger.success("Saved accounts and private keys to a file.")

    else:
        if not use_proxy:
            proxies = ["" for _ in range(len(mnemonics))]
        elif len(proxies) < len(mnemonics):
            proxies = [proxies[i % len(proxies)] for i in range(len(mnemonics))]

    logger.info("Starting...")
    semaphore = asyncio.Semaphore(value=threads)
    tasks = [
        asyncio.create_task(launch_wrapper(index, proxy, mnemonic, discord_token, twitter_token))
        for index, proxy, mnemonic, discord_token, twitter_token in zip(range(len(mnemonics)), proxies, mnemonics, discord_tokens, twitter_tokens)
    ]
    await asyncio.gather(*tasks)

    logger.success("Saved accounts and private keys to a file.")


async def account_flow(lock: asyncio.Lock, account_index: int, proxy: str, mnemonic: str, config: dict, task: int, discord_token: str, twitter_token: str):
    try:
        instance = model.elys.Elys(account_index, mnemonic, proxy, config, twitter_token, discord_token)

        if task == 1:
            await instance.bonus_block_flow()

        else:
            await instance.swap_flow()

        async with lock:
            with open("data/success_data.txt", "a") as f:
                f.write(f"{mnemonic}:{proxy}\n")

    except Exception as err:
        logger.error(f"{account_index} | Account flow failed: {err}")
        async with lock:
            await report_failed_key(mnemonic, proxy)


async def wrapper(function, attempts: int, *args, **kwargs):
    for _ in range(attempts):
        result = await function(*args, **kwargs)
        if isinstance(result, tuple) and result and isinstance(result[0], bool):
            if result[0]:
                return result
        elif isinstance(result, bool):
            if result:
                return True

    return result


async def report_failed_key(private_key: str, proxy: str):
    try:
        with open("data/failed_keys.txt", "a") as file:
            file.write(private_key + ":" + proxy + "\n")

    except Exception as err:
        logger.error(f"Error while reporting failed account: {err}")


async def mobile_proxy_wrapper(data):
    proxy, ip_change_link, mobile_proxy_queue, config, lock, private_keys, task, discord_token, twitter_token = data[:8]

    while not mobile_proxy_queue.empty():
        i = mobile_proxy_queue.get()

        try:
            for _ in range(3):
                try:
                    requests.get(f"{ip_change_link}",
                                 headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
                                 timeout=60)

                    await asyncio.sleep(config['change_ip_pause'])
                    logger.success(f"{i + 1} | Successfully changed IP")
                    break

                except Exception as err:
                    logger.error(f"{i + 1} | Mobile proxy error! Check your ip change link: {err}")
                    await asyncio.sleep(2)

            await account_flow(lock, i+1, proxy, private_keys[i], config, task, discord_token, twitter_token)

        except Exception as err:
            logger.error(f"{i + 1} | Mobile proxy flow error: {err}")
