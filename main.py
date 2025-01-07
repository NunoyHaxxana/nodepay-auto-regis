import asyncio
import random
import string
import time
from typing import Optional, Tuple, Dict
from curl_cffi import requests
from colorama import Fore, Style, init
from faker import Faker
from datetime import datetime
from capmonster_python import TurnstileTask
from twocaptcha import TwoCaptcha
from anticaptchaofficial.turnstileproxyless import turnstileProxyless
import cloudscraper
import re

init(autoreset=True)

def print_banner():
    print(f"\n{Fore.CYAN}{'='*45}")
    print(f"{Fore.YELLOW}       Nodepay Auto Referral Bot")
    print(f"{Fore.YELLOW}       github.com/nunoyhaxxana")
    print(f"{Fore.YELLOW}       do with your own risk")
    print(f"{Fore.CYAN}{'='*45}\n")

def log_step(message: str, type: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "info": Fore.LIGHTCYAN_EX,
        "success": Fore.LIGHTGREEN_EX,
        "error": Fore.LIGHTRED_EX,
        "warning": Fore.LIGHTYELLOW_EX
    }
    color = colors.get(type, Fore.WHITE)
    prefix = {
        "info": "ℹ",
        "success": "✓",
        "error": "✗",
        "warning": "⚠"
    }
    print(f"{Fore.WHITE}[{timestamp}] {color}{prefix.get(type, '•')} {message}{Style.RESET_ALL}")

class CaptchaConfig:
    WEBSITE_KEY = '0x4AAAAAAAx1CyDNL8zOEPe7'
    WEBSITE_URL = 'https://api.nodepay.org/api/auth/register'  # Updated URL

class CaptchaService:
    def __init__(self, service_name: str, api_key: str):
        self.service_name = service_name.lower()
        self.api_key = api_key
        if self.service_name == "capmonster":
            self.solver = TurnstileTask(api_key)
        elif self.service_name == "anticaptcha":
            self.solver = turnstileProxyless()
            self.solver.set_verbose(0)
            self.solver.set_key(api_key)
            self.solver.set_website_url(CaptchaConfig.WEBSITE_URL)
            self.solver.set_website_key(CaptchaConfig.WEBSITE_KEY)
        elif self.service_name == "2captcha":
            self.solver = TwoCaptcha(api_key)
        else:
            raise ValueError(f"Unknown captcha service: {service_name}")

    async def get_captcha_token(self):
        if self.service_name == "capmonster":
            task_id = self.solver.create_task(
                website_key=CaptchaConfig.WEBSITE_KEY,
                website_url=CaptchaConfig.WEBSITE_URL
            )
            return self.solver.join_task_result(task_id).get("token")
        elif self.service_name == "anticaptcha":
            return await asyncio.to_thread(self.solver.solve_and_return_solution)
        elif self.service_name == "2captcha":
            result = await asyncio.to_thread(
                lambda: self.solver.turnstile(
                    sitekey=CaptchaConfig.WEBSITE_KEY,
                    url=CaptchaConfig.WEBSITE_URL
                )
            )
            return result['code']

class ReferralClient:
    def __init__(self, base_email: str, name_play: str):
        self.base_email = base_email
        self.name_play = name_play
        self.session = requests.Session()
        self.scraper = cloudscraper.create_scraper()
        self.max_retries = 5
        self.proxies = self._load_proxies()
        self.proxy_index = 0

    def _validate_proxy(self, proxy: str) -> bool:
        # Regex to validate proxy format
        pattern = r'^(http|https):\/\/(\S+:\S+@)?\S+:\d+$'
        return re.match(pattern, proxy) is not None

    def _format_proxy(self, proxy: str) -> str:
        # Add http:// if missing
        if not proxy.startswith("http://") and not proxy.startswith("https://"):
            proxy = "http://" + proxy
        return proxy

    def _load_proxies(self) -> list:
        try:
            with open("proxies.txt", "r") as f:
                proxies = [line.strip() for line in f if line.strip()]
            formatted_proxies = [self._format_proxy(proxy) for proxy in proxies]
            valid_proxies = [proxy for proxy in formatted_proxies if self._validate_proxy(proxy)]

            if len(valid_proxies) < len(proxies):
                log_step("Some proxies in proxies.txt are invalid and were ignored.", "warning")
            log_step(f"Loaded {len(valid_proxies)} valid proxies.", "success")
            return valid_proxies
        except FileNotFoundError:
            log_step("proxies.txt not found. Running without proxies.", "warning")
            return []

    def _get_next_proxy(self) -> Optional[Dict[str, str]]:
        if not self.proxies:
            return None

        proxy = self.proxies[self.proxy_index]
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return {"http": proxy, "https": proxy}

    def _generate_email(self) -> str:
        random_number = random.randint(1, 9999)
        email = f"{self.base_email.split('@')[0]}+{self.name_play}{random_number:04d}@{self.base_email.split('@')[1]}"
        return email

    def _generate_password(self) -> str:
        password = (
            random.choice(string.ascii_uppercase) +
            ''.join(random.choices(string.digits, k=3)) +
            '@' +
            ''.join(random.choices(string.ascii_lowercase, k=8)) +
            random.choice(string.ascii_uppercase)
        )
        return password

    def _generate_credentials(self) -> Tuple[str, str, str]:
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = self._generate_email()
        password = self._generate_password()
        return username, email, password

    async def _make_request(self, method: str, url: str, json_data: dict, headers: dict) -> Optional[dict]:
        for attempt in range(1, self.max_retries + 1):
            try:
                proxy = self._get_next_proxy()
                log_step(f"Attempting request to URL: {url} with method: {method}", "info")
                log_step(f"Headers: {headers}", "info")
                log_step(f"Payload: {json_data}", "info")
                log_step(f"Using proxy: {proxy}", "info")

                response = await asyncio.to_thread(
                    lambda: self.scraper.request(
                        method=method,
                        url=url,
                        json=json_data,
                        headers=headers,
                        proxies=proxy,
                        timeout=30
                    )
                )

                log_step(f"Response Status Code: {response.status_code}", "info")
                log_step(f"Response Text: {response.text}", "info")

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 405:
                    log_step("Method Not Allowed (405): Check if the API URL and HTTP method are correct.", "error")
                    return None
                elif response.status_code == 429:
                    log_step("Rate Limited (429): Too many requests. Adding delay.", "warning")
                    await asyncio.sleep(10)  # Delay for 10 seconds
                elif response.status_code == 403:
                    log_step("Forbidden (403): Check if Cloudflare is blocking the request.", "error")
                    return None
                else:
                    log_step(f"Unexpected status code: {response.status_code}", "error")
            except Exception as e:
                log_step(f"Request error on attempt {attempt}: {e}", "error")
                if attempt == self.max_retries:
                    return None

    async def process_referral(self, ref_code: str, captcha_service: CaptchaService, api_url: str) -> Optional[dict]:
        username, email, password = self._generate_credentials()
        log_step(f"Generated credentials: Email={email}, Password={password}", "info")

        try:
            captcha_token = await captcha_service.get_captcha_token()
            log_step("Captcha token obtained", "success")
        except Exception as e:
            log_step(f"Captcha error: {e}", "error")
            return None

        register_data = {
            'email': email,
            'password': password,
            'username': username,
            'referral_code': ref_code,
            'recaptcha_token': captcha_token
        }

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://app.nodepay.org'
        }

        response = await self._make_request('POST', api_url, register_data, headers)

        if response and response.get("success"):
            log_step("Registration successful", "success")
            # Save to file
            with open("accounts.txt", "a") as f:
                f.write(f"Username: {username}\n")
                f.write(f"Email: {email}\n")
                f.write(f"Password: {password}\n")
                f.write(f"Referral Code: {ref_code}\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 40 + "\n")
            return {
                "username": username,
                "email": email,
                "password": password,
                "ref_code": ref_code
            }
        else:
            log_step("Registration failed or invalid response received.", "error")
            return None

async def main():
    print_banner()

    base_email = input(f"{Fore.GREEN}Enter base email (e.g., regisnodep@gmail.com): {Style.RESET_ALL}")
    name_play = input(f"{Fore.GREEN}Enter name_play (e.g., mynode): {Style.RESET_ALL}")
    ref_code = input(f"{Fore.GREEN}Enter referral code: {Style.RESET_ALL}")
    num_referrals = int(input(f"{Fore.GREEN}Enter number of referrals: {Style.RESET_ALL}"))

    api_url = CaptchaConfig.WEBSITE_URL

    print(f"\n{Fore.YELLOW}Available captcha services:{Style.RESET_ALL}")
    print(f"1. Capmonster")
    print(f"2. Anticaptcha")
    print(f"3. 2Captcha{Style.RESET_ALL}")
    service_choice = input(f"{Fore.GREEN}Choose captcha service (1-3): {Style.RESET_ALL}")
    api_key = input(f"{Fore.GREEN}Enter API key for captcha service: {Style.RESET_ALL}")

    service_map = {
        "1": "capmonster",
        "2": "anticaptcha",
        "3": "2captcha"
    }

    captcha_service = CaptchaService(service_map[service_choice], api_key)
    client = ReferralClient(base_email, name_play)

    for i in range(num_referrals):
        print(f"\n{Fore.CYAN}{'='*45}")
        log_step(f"Processing referral {i+1}/{num_referrals}", "info")

        result = await client.process_referral(ref_code, captcha_service, api_url)
        if result:
            log_step(f"Referral successful: {result['email']}", "success")
        else:
            log_step("Referral failed", "error")

        # Add a delay between requests to avoid rate limiting
        log_step("Adding delay to prevent rate limiting.", "info")
        await asyncio.sleep(5)  # Delay for 5 seconds

if __name__ == "__main__":
    asyncio.run(main())
