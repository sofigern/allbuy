import requests

import xml.etree.ElementTree as ET

from src.models.product import Product


class IntertoolManager:

    def __init__(self):
        self.xml_url = "https://s3.intertool.ua/b2c/files/clients/xml/ua/stock/xml_output.xml"
        self.xml_file = "xml_output.xml"
    
    def get_products(self, from_file: bool = False) -> list[Product]:
        if from_file:
            with open(self.xml_file, "r") as file:
                data = file.read()
        else:
            response = requests.get(self.xml_url)
            if response.status_code == 200:
                data = response.content
        
        root = ET.fromstring(data)
        offers = root.findall('.//offers/offer')
        return [
            Product(
                sku=offer.find('vendorCode').text,
                name=offer.find('name').text,
                price=float(offer.find('price').text),
                in_stock=offer.attrib['available'] == 'true',
            )
            for offer in offers
        ]
