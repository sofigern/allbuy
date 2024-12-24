from dataclasses import dataclass


@dataclass
class Delivery:
    id: int | None
    number: str
    cost: float | None

    @classmethod
    def from_np_kwargs(cls, **kwargs):
        return cls(
            id=kwargs.get("declaration_id"),
            number=kwargs.get("int_doc_number"),
            cost=kwargs.get("delivery_cost"),
        )

    @classmethod
    def from_up_kwargs(cls, **kwargs):
        return cls(
            id=None,
            number=kwargs.get("declarationId"),
            cost=kwargs.get("deliveryCost"),
        )

    @classmethod
    def from_rz_kwargs(cls, **kwargs):
        return cls(
            id=None,
            number=kwargs.get("declarationId"),
            cost=kwargs.get("deliveryCost"),
        )

    @classmethod
    def from_meest_kwargs(cls, **kwargs):
        return cls(
            id=None,
            number=kwargs.get("declarationRef"),
            cost=kwargs.get("deliveryCost"),
        )
