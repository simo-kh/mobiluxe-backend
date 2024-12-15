# models/product.py
from app import mongo

class Product:
    def __init__(self, name, description, price):
        self.name = name
        self.description = description
        self.price = price

    def insert_product(self):
        product_data = {
            "name": self.name,
            "description": self.description,
            "price": self.price
        }
        mongo.db.products.insert_one(product_data)
