from src.models.order import Order

from src.prom.client import PromAPIClient


class NotAllowedOrderError(Exception):
    reason = "Невідома"

    def __init__(self, order: Order):
        self.order = order

    def __str__(self):
        return (
            f"Замовлення {self.order.to_text()}"
            "------------------------------" + "\n"
            "Не може бути опрацьовано." + "\n"
            f"Причина: {self.reason}." + "\n"
            f"Статус замовлення: {self.order.status}." + "\n"
            f"Постачальник доставки: {self.order.delivery_option}." + "\n"
            f"Спосіб оплати: {self.order.payment_option}." + "\n"
            "------------------------------" + "\n"
            f"Деталі замовлення: {PromAPIClient.order_url(self.order.id)}"
        )


class NotAllowedOrderStatusError(NotAllowedOrderError):
    reason = "Недопустимий статус замовлення"


class DeliveryProviderNotAllowedError(NotAllowedOrderError):
    reason = "Недопустимий постачальник доставки"


class PaymentOptionDisabledError(NotAllowedOrderError):
    reason = "Недопустимий спосіб оплати"


class ModifiedDateIsTooOldError(NotAllowedOrderError):
    reason = "Дата оновлення замовлення занадто стара"


class IncompletePaymentError(NotAllowedOrderError):
    reason = "Замовлення очікує оплати і буде опрацьовано після її отримання"


class ReadyForDeliveryError(NotAllowedOrderError):
    reason = "Замовлення вже готове до відправлення"


class UnknownFinalizationError(NotAllowedOrderError):
    reason = "Невідомий алгоритм завершення замовлення"


class GenerationDeclarationError(Exception):
    def __init__(self, order: Order):
        self.order = order

    def __str__(self):
        return (
            f"Замовлення {self.order.to_text()}"
            "------------------------------" + "\n"
            "Помилка створення декларації." + "\n"
            "Очікуйте наступної спроби aбо обробіть замовлення вручну." + "\n"
            f"Статус замовлення: {self.order.status}." + "\n"
            f"Постачальник доставки: {self.order.delivery_option}." + "\n"
            f"Спосіб оплати: {self.order.payment_option}." + "\n"
            "------------------------------" + "\n"
            f"Деталі замовлення: {PromAPIClient.order_url(self.order.id)}"
        )
