import aiohttp


class SignalBot:
    def __init__(
        self,
        signal_service: str,
        phone_number: str,
        group_id: str,
        force: bool = False,
    ):
        self.service = signal_service
        self.phone_number = phone_number
        self.group_id = group_id

        self.force_msg = ""
        if force:
            self.force_msg = (
                "------------------------------" + "\n"
                "Це повідомлення відправлено в обов'язковому режимі." + "\n"
                "В цьому режимі відправка повідомлень може повторювати попередні." + "\n"
                "------------------------------"
            )

    async def send(self, message: str, debug: bool = False, notify: list[str] = None):
        recepient = self.group_id
        if debug:
            message = (
                "------------------------------" + "\n"
                "Це повідомлення відправлено в тестовому режимі." + "\n"
                "Ніяких справжніх дій не відбувається." + "\n"
                "------------------------------" + "\n"
                f"{message}"
            )
            recepient = self.phone_number

        if self.force_msg:
            message = f"{self.force_msg}\n{message}"
        
        mentions = []
        for phone in (notify or []):
            mentions.append({
                "author": phone,
                "length": 0,
                "start": len(message),
            })

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://{self.service}/v2/send",
                json={
                    "message": message,
                    "number": self.phone_number,
                    "recipients": [recepient],
                    "notify_self": False,
                    "mentions": mentions,
                }
            ) as resp:
                if 200 <= resp.status < 300:
                    print(f"Message sent successfully!. {await resp.text()}")
                else:
                    print(f"Failed to send message: {resp.status}, {await resp.text()}")
