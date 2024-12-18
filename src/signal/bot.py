import aiohttp


class SignalBot:
    def __init__(
        self,
        signal_service: str,
        phone_number: str,
        group_id: str,
    ):
        self.service = signal_service
        self.phone_number = phone_number
        self.group_id = group_id

    async def send(self, message: str, debug: bool = True):
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
           
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://{self.service}/v2/send",
                json={
                    "message": message,
                    "number": self.phone_number,
                    "recipients": [recepient],
                    "notify_self": False,
                }
            ) as resp:
                if 200 <= resp.status < 300:
                    print(f"Message sent successfully!. {await resp.text()}")
                else:
                    print(f"Failed to send message: {resp.status}, {await resp.text()}")
